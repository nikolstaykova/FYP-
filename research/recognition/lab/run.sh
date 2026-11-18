#!/bin/zsh
# Start the parts lab (see server.py). Add --lan to open it from a phone on the same Wi-Fi.
HERE=${0:A:h}
ROOT=$HERE/../../..
# the database server (Neo4j on Hetzner): open the SSH tunnel to it first, when .env names it
DB_HOST=$(grep -E '^PINPOINT_DB_HOST=' $ROOT/.env 2>/dev/null | cut -d= -f2-)
if [[ -n $DB_HOST ]]; then
  PINPOINT_DB_HOST=$DB_HOST $ROOT/deploy/neo4j/tunnel.sh || echo "database tunnel did not start: the lessons come from the files"
fi
exec $ROOT/.venv-research/bin/python $HERE/server.py "$@"
