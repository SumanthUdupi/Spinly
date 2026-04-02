#!/usr/bin/env bash
# =============================================================================
# start-services.sh — Start MariaDB, Redis, and Frappe bench
# Runs via devcontainer postStartCommand on every container start/resume.
# Safe to run manually at any time.
# =============================================================================
set -euo pipefail

BENCH_DIR="/workspaces/Frappe/frappe-bench"
SITE_NAME="dev.localhost"
DB_ROOT_PASS="frappe"
LOG_FILE="$BENCH_DIR/logs/bench-start.log"

echo ""
echo "=============================================="
echo "  Starting Frappe Development Services"
echo "=============================================="
echo ""

# Abort early if bench hasn't been set up yet (setup-bench.sh not run)
if [ ! -d "$BENCH_DIR/apps/frappe" ]; then
    echo "  Bench not set up yet. Run setup-bench.sh first."
    exit 0
fi

# ------------------------------------------------------------------------------
# 1. MariaDB
# ------------------------------------------------------------------------------
echo "[1/4] MariaDB..."
if sudo service mariadb status > /dev/null 2>&1; then
    echo "      Already running."
else
    sudo service mariadb start
    # Wait up to 15 s for MariaDB to accept connections
    for i in $(seq 1 15); do
        if mysqladmin ping -h 127.0.0.1 -u root -p"$DB_ROOT_PASS" --silent 2>/dev/null; then
            echo "      Started (${i}s)."
            break
        fi
        sleep 1
    done
fi

# ------------------------------------------------------------------------------
# 1b. DB resurrection — containers can be reset (e.g. Codespaces rebuild) which
#     wipes MariaDB data while workspace files (site_config.json) survive.
#     Detect this mismatch and recreate the database + user automatically so
#     developers never see "Access denied" errors on first start.
# ------------------------------------------------------------------------------
SITE_CFG="$BENCH_DIR/sites/$SITE_NAME/site_config.json"
if [ -f "$SITE_CFG" ]; then
    DB_NAME=$(python3 -c "import json; d=json.load(open('$SITE_CFG')); print(d['db_name'])")
    DB_PASS=$(python3 -c "import json; d=json.load(open('$SITE_CFG')); print(d['db_password'])")

    if ! mysql -u root -p"$DB_ROOT_PASS" -h 127.0.0.1 -e "USE \`$DB_NAME\`;" 2>/dev/null; then
        echo "      Site database missing (container reset?) — recreating..."
        mysql -u root -p"$DB_ROOT_PASS" -h 127.0.0.1 << SQLEOF
CREATE DATABASE IF NOT EXISTS \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$DB_NAME'@'%' IDENTIFIED BY '$DB_PASS';
CREATE USER IF NOT EXISTS '$DB_NAME'@'localhost' IDENTIFIED BY '$DB_PASS';
GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_NAME'@'%';
GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_NAME'@'localhost';
FLUSH PRIVILEGES;
SQLEOF
        echo "      Restoring site schema via migrate (this may take a few minutes)..."
        (cd "$BENCH_DIR" && bench --site "$SITE_NAME" migrate)
        echo "      Site database restored."
    else
        echo "      Site database OK."
    fi
fi

# ------------------------------------------------------------------------------
# 2. Redis cache (port 13000)
# ------------------------------------------------------------------------------
echo "[2/4] Redis..."
cd "$BENCH_DIR"
if redis-cli -p 13000 ping > /dev/null 2>&1; then
    echo "      Cache (13000): already running."
else
    redis-server config/redis_cache.conf --daemonize yes
    sleep 1
    echo "      Cache (13000): $(redis-cli -p 13000 ping)"
fi

if redis-cli -p 11000 ping > /dev/null 2>&1; then
    echo "      Queue (11000): already running."
else
    redis-server config/redis_queue.conf --daemonize yes
    sleep 1
    echo "      Queue (11000): $(redis-cli -p 11000 ping)"
fi

# ------------------------------------------------------------------------------
# 3. Bench (Procfile via honcho) — backgrounded so postStartCommand returns
# ------------------------------------------------------------------------------
echo "[3/4] Starting Frappe bench..."

# Kill any stale bench processes before starting fresh
pkill -f "honcho" 2>/dev/null || true
pkill -f "gunicorn.*frappe" 2>/dev/null || true
sleep 1

mkdir -p "$BENCH_DIR/logs"
nohup bash -c "cd '$BENCH_DIR' && bench start" >> "$LOG_FILE" 2>&1 &
BENCH_PID=$!
echo "      Bench started (PID $BENCH_PID)."
echo "      Logs: $LOG_FILE"

# ------------------------------------------------------------------------------
# 4. Clear cache on startup to avoid stale module errors
# ------------------------------------------------------------------------------
echo "[4/4] Clearing cache..."
sleep 3   # Give bench a moment to initialise before clearing
(cd "$BENCH_DIR" && bench --site "$SITE_NAME" clear-cache 2>/dev/null) || true
echo "      Done."

# ------------------------------------------------------------------------------
# 5. SSH server — lets testers port-forward to bench without any external service
# ------------------------------------------------------------------------------
echo "[5/5] SSH tunnel server..."
bash /workspaces/Frappe/scripts/setup-ssh.sh
echo ""
echo "=============================================="
echo "  All services running."
echo ""
echo "  Web UI  : http://localhost:8000"
echo "  User    : Administrator / admin"
echo ""
echo "  Tail logs : tail -f $LOG_FILE"
echo "=============================================="
echo ""
