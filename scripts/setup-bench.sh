#!/usr/bin/env bash
# =============================================================================
# setup-bench.sh — One-time Frappe + ERPNext + Dynamic Tooltip setup
# Runs via devcontainer postCreateCommand on first container creation.
# Idempotent: safe to re-run; skips steps already completed.
# =============================================================================
set -euo pipefail

BENCH_DIR="/workspaces/Frappe/frappe-bench"
SITE_NAME="dev.localhost"
DB_ROOT_PASS="frappe"
ADMIN_PASS="admin"

echo ""
echo "=============================================="
echo "  Frappe + ERPNext Dev Environment Setup"
echo "=============================================="
echo ""

# ------------------------------------------------------------------------------
# 1. System dependencies
# ------------------------------------------------------------------------------
echo "[1/10] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq \
    redis-server \
    mariadb-client \
    mariadb-server \
    libssl-dev \
    cron \
    curl \
    openssh-client
echo "       Done."

# ------------------------------------------------------------------------------
# 2. Install bench CLI
# ------------------------------------------------------------------------------
echo "[2/10] Installing frappe-bench CLI..."
pip3 install --quiet --upgrade frappe-bench
echo "       Done."

# ------------------------------------------------------------------------------
# 3. Init bench (idempotent — skip if frappe app already present)
# ------------------------------------------------------------------------------
echo "[3/10] Initialising bench at $BENCH_DIR..."
if [ ! -d "$BENCH_DIR/apps/frappe" ]; then
    bench init \
        --skip-redis-config-generation \
        --python python3.14 \
        "$BENCH_DIR"
    echo "       Bench initialised."
else
    echo "       Bench already exists — skipping init."
fi

cd "$BENCH_DIR"

# ------------------------------------------------------------------------------
# 3b. Ensure Node.js dependencies are fully installed in frappe app
#     bench init runs yarn install, but a partial install or cache corruption
#     can leave packages like fast-glob incomplete.  A targeted reinstall here
#     guarantees a clean state before any `bench build` or `bench get-app` call.
# ------------------------------------------------------------------------------
echo "[3b/10] Verifying Node.js dependencies in frappe app..."
(cd "$BENCH_DIR/apps/frappe" && yarn install --frozen-lockfile --silent)
echo "        Done."

# ------------------------------------------------------------------------------
# 4. Generate Redis config files & Procfile from bench templates
# ------------------------------------------------------------------------------
echo "[4/10] Generating Redis configs and Procfile..."
bench setup redis
bench setup procfile

# Patch Procfile: add --proxy so Frappe trusts forwarded headers from tunnels
if grep -q "bench serve --port" Procfile && ! grep -q "\-\-proxy" Procfile; then
    sed -i 's/bench serve --port/bench serve --proxy --port/' Procfile
    echo "       Procfile patched with --proxy flag."
else
    echo "       Procfile already patched — skipping."
fi
echo "       Done."

# ------------------------------------------------------------------------------
# 5. Start MariaDB and secure root access for bench
# ------------------------------------------------------------------------------
echo "[5/10] Starting MariaDB and setting root password..."
sudo service mariadb start
sleep 2
# Set root password (idempotent — suppress error if already set)
sudo mysql -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$DB_ROOT_PASS'; FLUSH PRIVILEGES;" 2>/dev/null \
    || sudo mysql -u root -p"$DB_ROOT_PASS" -e "SELECT 1;" 2>/dev/null \
    || true
echo "       MariaDB ready."

# ------------------------------------------------------------------------------
# 6. Get ERPNext app (idempotent)
# ------------------------------------------------------------------------------
echo "[6/10] Getting ERPNext app..."
if [ ! -d "$BENCH_DIR/apps/erpnext" ]; then
    bench get-app erpnext
    echo "       ERPNext fetched."
else
    echo "       ERPNext already present — skipping."
fi

# ------------------------------------------------------------------------------
# 7. Get Dynamic Tooltip app (idempotent)
#    Use --skip-assets because dynamic_tooltip has no frontend bundle;
#    attempting to build it raises an esbuild TypeError and aborts the install.
# ------------------------------------------------------------------------------
echo "[7/10] Getting Dynamic Tooltip app..."
if [ ! -d "$BENCH_DIR/apps/dynamic_tooltip" ]; then
    bench get-app https://github.com/SumanthUdupi/Dynamic_Tooltip_Frappe --skip-assets
    echo "       Dynamic Tooltip fetched."
else
    echo "       Dynamic Tooltip already present — skipping."
fi

# Ensure dynamic_tooltip is registered in apps.txt
if ! grep -qx "dynamic_tooltip" "$BENCH_DIR/sites/apps.txt" 2>/dev/null; then
    echo "dynamic_tooltip" >> "$BENCH_DIR/sites/apps.txt"
    echo "       Registered dynamic_tooltip in apps.txt."
fi

# ------------------------------------------------------------------------------
# 8. Start Redis (needed before new-site)
# ------------------------------------------------------------------------------
echo "[8/10] Starting Redis instances..."
redis-cli -p 13000 ping > /dev/null 2>&1 \
    || redis-server config/redis_cache.conf --daemonize yes
redis-cli -p 11000 ping > /dev/null 2>&1 \
    || redis-server config/redis_queue.conf --daemonize yes
sleep 1
echo "       Redis cache (13000): $(redis-cli -p 13000 ping)"
echo "       Redis queue (11000): $(redis-cli -p 11000 ping)"

# ------------------------------------------------------------------------------
# 9. Create site with Frappe + ERPNext + Dynamic Tooltip (idempotent)
# ------------------------------------------------------------------------------
echo "[9/10] Creating site '$SITE_NAME'..."
if [ ! -f "$BENCH_DIR/sites/$SITE_NAME/site_config.json" ]; then
    bench new-site "$SITE_NAME" \
        --db-root-password "$DB_ROOT_PASS" \
        --admin-password "$ADMIN_PASS" \
        --install-app erpnext
    echo "       Site created with frappe + erpnext."
else
    echo "       Site already exists — skipping new-site."
fi

# Install dynamic_tooltip on the site (idempotent via grep check)
INSTALLED=$(bench --site "$SITE_NAME" list-apps 2>/dev/null || true)
if echo "$INSTALLED" | grep -q "dynamic_tooltip"; then
    echo "       dynamic_tooltip already installed on site — skipping."
else
    bench --site "$SITE_NAME" install-app dynamic_tooltip
    echo "       dynamic_tooltip installed on site."
fi

# Set as the default site
bench use "$SITE_NAME"

# Run migration to sync all DocTypes (includes dynamic_tooltip schema)
echo "       Running site migration..."
bench --site "$SITE_NAME" migrate
echo "       Migration complete."

# Clear cache
bench --site "$SITE_NAME" clear-cache
echo "       Cache cleared."

# ------------------------------------------------------------------------------
# 10. Tune common_site_config.json
# ------------------------------------------------------------------------------
echo "[10/10] Tuning common_site_config.json..."
python3 - <<'PYEOF'
import json, pathlib
cfg_path = pathlib.Path("sites/common_site_config.json")
cfg = json.loads(cfg_path.read_text())
cfg["gunicorn_workers"] = 2   # 25 is excessive for dev; saves RAM
cfg_path.write_text(json.dumps(cfg, indent=1) + "\n")
print("        gunicorn_workers set to 2.")
PYEOF

echo ""
echo "=============================================="
echo "  Setup complete!"
echo ""
echo "  Site  : $SITE_NAME"
echo "  Login : http://localhost:8000"
echo "  User  : Administrator"
echo "  Pass  : $ADMIN_PASS"
echo ""
echo "  Start services : bash /workspaces/Frappe/scripts/start-services.sh"
echo "  Public URL     : bash /workspaces/Frappe/scripts/tunnel.sh"
echo "=============================================="
echo ""
