#!/usr/bin/env bash
# =============================================================================
# setup-docker-server.sh — First-time Docker server setup
#
# Run this ONCE to pull images, create the site, and start everything.
# After this, every PC restart brings everything back automatically.
#
# Usage:
#   bash /workspaces/Frappe/scripts/setup-docker-server.sh
# =============================================================================
set -euo pipefail

SERVER_DIR="/workspaces/Frappe/server"

echo ""
echo "=============================================="
echo "  ERPNext Docker Server — First-Time Setup"
echo "=============================================="
echo ""

# Check Docker is available
if ! docker info > /dev/null 2>&1; then
    echo "  ERROR: Docker is not running."
    echo "  Start Docker Desktop and try again."
    exit 1
fi

cd "$SERVER_DIR"

echo "[1/4] Pulling Docker images (frappe/erpnext:v16.8.2)..."
echo "      This may take a few minutes on first run."
docker compose pull
echo "      Done."
echo ""

echo "[2/4] Starting database and Redis..."
docker compose up -d db redis-cache redis-queue
echo "      Waiting for MariaDB to be healthy..."
for i in $(seq 1 30); do
    if docker compose exec db mysqladmin ping -h localhost --silent 2>/dev/null; then
        echo "      MariaDB ready (${i}s)."
        break
    fi
    sleep 2
done
echo ""

echo "[3/4] Running configurator and creating site with ERPNext..."
echo "      This may take 3-5 minutes."
docker compose up configurator create-site
echo "      Done."
echo ""

echo "[4/4] Starting all services..."
docker compose up -d
echo ""

echo "=============================================="
echo "  Setup complete!"
echo ""
echo "  Site URL  : http://localhost:8080"
echo "  Login     : Administrator"
echo "  Password  : admin  (or your ADMIN_PASSWORD from server/.env)"
echo ""
echo "  IMPORTANT: Docker Desktop auto-starts on Windows login."
echo "  All containers have restart: unless-stopped, so the site"
echo "  comes back automatically after every PC restart — no action needed."
echo ""
echo "  To share a public URL (no registration required):"
echo "    bash /workspaces/Frappe/scripts/tunnel.sh"
echo ""
echo "  Useful commands:"
echo "    docker compose -f $SERVER_DIR/docker-compose.yml logs -f   # view logs"
echo "    docker compose -f $SERVER_DIR/docker-compose.yml down       # stop all"
echo "    docker compose -f $SERVER_DIR/docker-compose.yml up -d      # start all"
echo "=============================================="
echo ""
