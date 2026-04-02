#!/usr/bin/env bash
# =============================================================================
# setup-ssh.sh
#
# Installs and starts an SSH server inside the devcontainer on port 2222.
# Creates a dedicated user  spinly / Spinly@access  for tester SSH tunnels.
#
# Called automatically from start-services.sh on every container start.
# Safe to run manually at any time.
# =============================================================================
set -euo pipefail

SSH_PORT=2222
SSH_USER="spinly"
SSH_PASS="Spinly@access"
SSHD_CONFIG="/etc/ssh/sshd_config"

# ── 1. Install openssh-server if missing ──────────────────────────────────────
if ! command -v sshd &>/dev/null; then
    echo "  [SSH] Installing openssh-server..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq openssh-server
fi

# ── 2. Create SSH user ────────────────────────────────────────────────────────
if ! id "$SSH_USER" &>/dev/null; then
    sudo useradd -m -s /bin/bash "$SSH_USER"
fi
echo "$SSH_USER:$SSH_PASS" | sudo chpasswd

# ── 3. Configure sshd ────────────────────────────────────────────────────────
sudo tee /etc/ssh/sshd_config.d/spinly.conf > /dev/null << EOF
Port $SSH_PORT
PasswordAuthentication yes
AllowTcpForwarding yes
GatewayPorts no
X11Forwarding no
PrintMotd no
EOF

# Ensure the privilege separation directory exists (required by sshd)
sudo mkdir -p /run/sshd

# ── 4. Start sshd (kill stale one first) ─────────────────────────────────────
sudo pkill -f "sshd -D" 2>/dev/null || true
sleep 1
sudo /usr/sbin/sshd -D -f "$SSHD_CONFIG" &
disown $!

sleep 1

# ── 5. Print the tester command ───────────────────────────────────────────────
# Get the Windows host IP (the default gateway from inside WSL2/container)
HOST_IP=$(ip route | awk '/default/ {print $3; exit}')

echo ""
echo "  ┌─────────────────────────────────────────────────────┐"
echo "  │  SSH tunnel ready on port $SSH_PORT                      │"
echo "  │                                                     │"
echo "  │  Find your Windows IP:  run  ipconfig  on Windows  │"
echo "  │  Look for: Ethernet / Wi-Fi  IPv4 Address           │"
echo "  │                                                     │"
echo "  │  Share this command with testers:                   │"
echo "  │                                                     │"
echo "  │  ssh -L 8000:127.0.0.1:8000 \\                      │"
echo "  │      -L 9000:127.0.0.1:9000 \\                      │"
echo "  │      -p $SSH_PORT spinly@YOUR_WINDOWS_IP                 │"
echo "  │                                                     │"
echo "  │  Password : $SSH_PASS                          │"
echo "  │  Then open: http://127.0.0.1:8000                  │"
echo "  │  Login  :  Administrator / admin                   │"
echo "  └─────────────────────────────────────────────────────┘"
echo ""
