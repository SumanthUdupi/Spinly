#!/usr/bin/env bash
# =============================================================================
# server-setup.sh
#
# Run this ONCE on any Ubuntu 22.04 machine (your own PC, WSL2, or a cloud VM)
# as root to natively install Frappe + ERPNext + Spinly — NO Docker required.
#
# What it does:
#   - Installs Python 3.11, Node.js 18, MariaDB, Redis, nginx, Supervisor
#   - Creates a 'frappe' user and initialises a Frappe bench
#   - Installs ERPNext and creates the Spinly site
#   - Configures Supervisor to keep all processes running 24/7
#   - Locks nginx to loopback-only (testers access via SSH tunnel)
#   - Creates the SSH tester user
#
# How to run:
#   sudo bash server-setup.sh
#
# Tester access (after setup):
#   ssh -L 8000:127.0.0.1:8000 -L 9000:127.0.0.1:9000 frappe@YOUR_MACHINE_IP
#   Password: Exponent@15mins
#   Then open: http://127.0.0.1:8000
# =============================================================================
set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
SSH_USER="frappe"
SSH_PASS="Exponent@15mins"
FRAPPE_ADMIN_PASS="admin"
DB_ROOT_PASS="frappe_db_secret"
SITE_NAME="spinly.local"
BENCH_DIR="/home/frappe/frappe-bench"
APP_PORT="8000"
SOCKETIO_PORT="9000"

# ── Colours ───────────────────────────────────────────────────────────────────
G='\033[0;32m'; B='\033[0;34m'; Y='\033[1;33m'; N='\033[0m'
ok()   { echo -e "${G}[OK]${N}  $*"; }
info() { echo -e "${B}[..] $*${N}"; }
warn() { echo -e "${Y}[!!] $*${N}"; }

[[ $(id -u) -eq 0 ]] || { echo "Run as root: sudo bash server-setup.sh"; exit 1; }

echo ""
echo "================================================="
echo "  Spinly Native Server Setup"
echo "================================================="
echo ""

# ── WSL2 systemd check ───────────────────────────────────────────────────────
# Supervisor and nginx need systemd. On WSL2, enable it if not already active.
if grep -qi microsoft /proc/version 2>/dev/null; then
    warn "Running inside WSL2."
    if ! systemctl is-system-running &>/dev/null; then
        info "Enabling systemd in WSL2..."
        mkdir -p /etc/wsl.conf.d 2>/dev/null || true
        cat >> /etc/wsl.conf << 'EOF'
[boot]
systemd=true
EOF
        warn "systemd has been enabled in /etc/wsl.conf."
        warn "Restart WSL2 now with 'wsl --shutdown' from PowerShell,"
        warn "then re-run this script."
        exit 0
    fi
fi

# ── 1. System packages ───────────────────────────────────────────────────────
info "Installing system packages..."
apt-get update -qq
apt-get install -y -qq software-properties-common
# deadsnakes PPA for Python 3.12 (frappe v16 uses type-alias syntax requiring 3.12+)
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update -qq
apt-get install -y -qq \
    python3.12 python3.12-dev python3.12-venv \
    python3.14 python3.14-dev python3.14-venv python3-pip \
    git curl mariadb-server redis-server nginx supervisor \
    wkhtmltopdf libmysqlclient-dev build-essential pkg-config \
    libjpeg-dev libpng-dev ufw
ok "System packages installed."

# ── 2. Node.js 18 ─────────────────────────────────────────────────────────────
if ! node --version 2>/dev/null | grep -q "^v2[4-9]"; then
    info "Installing Node.js 24..."
    curl -fsSL https://deb.nodesource.com/setup_24.x | bash - 2>/dev/null
    apt-get install -y -qq nodejs
    ok "Node.js $(node --version) installed."
else
    ok "Node.js $(node --version) already present."
fi

# Install yarn globally (bench requires it)
npm install -g yarn --silent
ok "Yarn installed."

# ── 3. Configure MariaDB ──────────────────────────────────────────────────────
info "Configuring MariaDB..."
systemctl enable mariadb && systemctl start mariadb

cat > /etc/mysql/conf.d/frappe.cnf << 'EOF'
[mysqld]
character-set-server  = utf8mb4
collation-server      = utf8mb4_unicode_ci
skip-character-set-client-handshake
skip-innodb-read-only-compressed
EOF

# Set root password (safe to run even if password is already set)
mysql -u root 2>/dev/null << SQLEOF || true
ALTER USER 'root'@'localhost' IDENTIFIED BY '$DB_ROOT_PASS';
FLUSH PRIVILEGES;
SQLEOF

systemctl restart mariadb

# Wait for MariaDB to be ready
for i in $(seq 1 20); do
    mysqladmin ping -h 127.0.0.1 -u root -p"$DB_ROOT_PASS" --silent 2>/dev/null && break
    sleep 1
done
ok "MariaDB configured (root password set)."

# ── 4. Create 'frappe' Linux user ────────────────────────────────────────────
if ! id "$SSH_USER" &>/dev/null; then
    info "Creating user '$SSH_USER'..."
    useradd -m -s /bin/bash "$SSH_USER"
    ok "User '$SSH_USER' created."
else
    ok "User '$SSH_USER' already exists."
fi

# ── 5. Install bench CLI ──────────────────────────────────────────────────────
info "Installing frappe-bench CLI..."
pip3 install frappe-bench --quiet
ok "frappe-bench CLI installed."

# ── 6. Initialise bench and install ERPNext ───────────────────────────────────
if [ ! -d "$BENCH_DIR" ]; then
    info "Initialising Frappe bench (this downloads ~1.5 GB — takes 5–15 min)..."
    sudo -u "$SSH_USER" bash -c "
        cd /home/$SSH_USER
        bench init frappe-bench \
            --frappe-branch version-16 \
            --python python3.14 \
            --skip-redis-config-generation
    "
    ok "Bench initialised."
else
    ok "Bench directory already exists — skipping init."
fi

if [ ! -d "$BENCH_DIR/apps/erpnext" ]; then
    info "Fetching ERPNext app (this may take a few minutes)..."
    sudo -u "$SSH_USER" bash -c "
        cd $BENCH_DIR
        bench get-app erpnext --branch version-16
    "
    ok "ERPNext fetched."
else
    ok "ERPNext already present."
fi

# ── 7. Create site ───────────────────────────────────────────────────────────
if [ ! -d "$BENCH_DIR/sites/$SITE_NAME" ]; then
    info "Creating site '$SITE_NAME' and installing ERPNext..."
    sudo -u "$SSH_USER" bash -c "
        cd $BENCH_DIR
        bench new-site $SITE_NAME \
            --db-root-password $DB_ROOT_PASS \
            --admin-password $FRAPPE_ADMIN_PASS \
            --install-app erpnext
        bench --site $SITE_NAME set-default
    "
    ok "Site '$SITE_NAME' created."
else
    ok "Site '$SITE_NAME' already exists — skipping."
fi

# ── 8. Production setup (Supervisor + nginx) ──────────────────────────────────
info "Configuring Supervisor and nginx for production..."
cd "$BENCH_DIR"
sudo -u "$SSH_USER" bash -c "cd $BENCH_DIR && bench setup production $SSH_USER --yes" || true
ok "Supervisor and nginx configured."

# ── 9. Lock nginx to loopback only ───────────────────────────────────────────
# bench setup production creates nginx listening on port 80 publicly.
# We change it to 127.0.0.1:8000 so the app is only accessible via SSH tunnel.
info "Restricting nginx to loopback (SSH tunnel security)..."
NGINX_CONF="/etc/nginx/conf.d/$SITE_NAME.conf"
if [ ! -f "$NGINX_CONF" ]; then
    # bench may put it in sites-enabled
    NGINX_CONF=$(find /etc/nginx -name "*.conf" | xargs grep -l "$SITE_NAME" 2>/dev/null | head -1 || true)
fi

if [ -n "$NGINX_CONF" ] && [ -f "$NGINX_CONF" ]; then
    sed -i "s/listen 80;/listen 127.0.0.1:$APP_PORT;/g" "$NGINX_CONF"
    sed -i "s/listen \[::\]:80;.*//g" "$NGINX_CONF"
    nginx -t && systemctl reload nginx
    ok "nginx locked to 127.0.0.1:$APP_PORT."
else
    warn "Could not find nginx conf for '$SITE_NAME' — check /etc/nginx manually."
    warn "Change 'listen 80' to 'listen 127.0.0.1:$APP_PORT' for SSH-tunnel-only access."
fi

# ── 10. SSH user for testers ──────────────────────────────────────────────────
info "Setting up SSH tester access..."
echo "$SSH_USER:$SSH_PASS" | chpasswd
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/^#*KbdInteractiveAuthentication.*/KbdInteractiveAuthentication yes/' /etc/ssh/sshd_config
systemctl reload sshd
ok "SSH tester access enabled (user: $SSH_USER, port: 22)."

# ── 11. Firewall ──────────────────────────────────────────────────────────────
info "Configuring firewall (port 22 only)..."
ufw --force reset > /dev/null
ufw default deny incoming > /dev/null
ufw default allow outgoing > /dev/null
ufw allow 22/tcp > /dev/null
ufw --force enable > /dev/null
ok "Firewall: port 22 open. Port 8000/9000 internal only (SSH tunnel required)."

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "================================================="
echo -e "${G}  Setup complete!${N}"
echo "================================================="
echo ""
echo "  Frappe admin login"
echo "    Username : Administrator"
echo "    Password : $FRAPPE_ADMIN_PASS"
echo ""
echo "  Share this command with testers:"
echo ""
echo "    ssh -L $APP_PORT:127.0.0.1:$APP_PORT -L $SOCKETIO_PORT:127.0.0.1:$SOCKETIO_PORT $SSH_USER@YOUR_MACHINE_IP"
echo "    Password: $SSH_PASS"
echo ""
echo "    Then open: http://127.0.0.1:$APP_PORT"
echo ""
echo "  Service management:"
echo "    sudo supervisorctl status          # check all processes"
echo "    sudo supervisorctl restart all     # restart everything"
echo "    sudo systemctl status nginx        # nginx status"
echo "    sudo systemctl status mariadb      # database status"
echo "    tail -f $BENCH_DIR/logs/*.log      # live logs"
echo "================================================="
