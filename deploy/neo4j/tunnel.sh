#!/usr/bin/env bash
# The Mac's way to the database server: an encrypted SSH tunnel, so localhost:7687 on the Mac is Neo4j on the server
# (whose port is closed to the internet).
#
#   PINPOINT_DB_HOST=ubuntu@<server ip> deploy/neo4j/tunnel.sh     # start in the background (nothing if already up)
#   deploy/neo4j/tunnel.sh stop
set -euo pipefail
KEY="${PINPOINT_DB_KEY:-$HOME/.ssh/pinpoint_db}"
MATCH="7687:127.0.0.1:7687"
if [ "${1:-}" = "stop" ]; then
  pkill -f "$MATCH" || true
  exit 0
fi
: "${PINPOINT_DB_HOST:?set PINPOINT_DB_HOST=ubuntu@<server ip>}"
pgrep -f "$MATCH" >/dev/null && exit 0
# -f -N: in the background, no shell, only the tunnel; keep-alives so a quiet tunnel is not dropped
ssh -f -N -i "$KEY" -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -o StrictHostKeyChecking=accept-new -L "$MATCH" -L 7474:127.0.0.1:7474 "$PINPOINT_DB_HOST"
echo "tunnel up: bolt://localhost:7687 -> $PINPOINT_DB_HOST"
