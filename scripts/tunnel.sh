#!/usr/bin/env bash
# =============================================================================
# tunnel.sh — Expose Frappe via a free public HTTPS URL
#
# Uses localhost.run (SSH-based, zero registration required).
# The URL it prints can be shared with anyone — they just open it in a browser
# and log in with their Frappe credentials.
#
# Usage:
#   bash /workspaces/Frappe/scripts/tunnel.sh          # default port 8000
#   bash /workspaces/Frappe/scripts/tunnel.sh 8080     # custom port
#
# Press Ctrl+C to close the tunnel.
# =============================================================================

LOCAL_PORT="${1:-8080}"

echo ""
echo "=============================================="
echo "  Frappe Public Tunnel"
echo "=============================================="
echo ""
echo "  Exposing http://localhost:$LOCAL_PORT to the internet."
echo "  No registration or account required."
echo ""
echo "  A public HTTPS URL will appear below."
echo "  Share it — others open it in a browser and log in."
echo "  Press Ctrl+C to stop."
echo ""

# Warn if nothing is listening on the local port
if ! curl -s --max-time 2 "http://localhost:$LOCAL_PORT" > /dev/null 2>&1; then
    echo "  WARNING: Frappe does not appear to be running on port $LOCAL_PORT."
    echo "  Start it first:  cd /workspaces/Frappe/server && docker compose up -d"
    echo "  Then re-run this script."
    echo ""
fi

echo "----------------------------------------------"
echo "  Connecting to localhost.run ..."
echo "----------------------------------------------"
echo ""

# Primary: localhost.run
#   - SSH reverse tunnel: remote port 80 → local port $LOCAL_PORT
#   - StrictHostKeyChecking=accept-new: trust on first connection, no prompt
#   - ServerAlive*: detect broken connections and exit cleanly
ssh \
    -o StrictHostKeyChecking=accept-new \
    -o ServerAliveInterval=30 \
    -o ServerAliveCountMax=3 \
    -o ExitOnForwardFailure=yes \
    -R "80:localhost:$LOCAL_PORT" \
    nokey@localhost.run

# Fallback (uncomment if localhost.run is unreachable)
# echo "Falling back to serveo.net..."
# ssh \
#     -o StrictHostKeyChecking=accept-new \
#     -o ServerAliveInterval=30 \
#     -o ServerAliveCountMax=3 \
#     -R "frappe-dev:80:localhost:$LOCAL_PORT" \
#     serveo.net
