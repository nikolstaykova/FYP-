#!/usr/bin/env bash
# Neo4j Community Edition (free) on a small Linux server (Oracle Cloud Always Free, Ubuntu), for Pinpoint.
#
# The database listens only on the server itself (127.0.0.1): nothing is open to the internet. The Mac reaches it
# through an SSH tunnel (deploy/neo4j/tunnel.sh), so NEO4J_URI stays bolt://localhost:7687 on the Mac.
#
# Run on the server:   NEO4J_PASSWORD='...' bash setup.sh
# (the password is passed in, never written to the repo)
set -euo pipefail
: "${NEO4J_PASSWORD:?set NEO4J_PASSWORD}"

if ! command -v docker >/dev/null; then
  sudo apt-get update -y
  sudo apt-get install -y docker.io
  sudo systemctl enable --now docker
fi

sudo mkdir -p /srv/neo4j/data /srv/neo4j/logs
sudo docker rm -f pinpoint-neo4j 2>/dev/null || true
sudo docker run -d --name pinpoint-neo4j --restart unless-stopped \
  -p 127.0.0.1:7687:7687 -p 127.0.0.1:7474:7474 \
  -v /srv/neo4j/data:/data -v /srv/neo4j/logs:/logs \
  -e NEO4J_AUTH="neo4j/${NEO4J_PASSWORD}" \
  -e NEO4J_server_memory_heap_initial__size=512m \
  -e NEO4J_server_memory_heap_max__size=1g \
  -e NEO4J_server_memory_pagecache_size=512m \
  neo4j:5-community

echo "waiting for Neo4j..."
for i in $(seq 1 60); do
  if sudo docker exec pinpoint-neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" "RETURN 1" >/dev/null 2>&1; then
    echo "Neo4j is up (bolt on 127.0.0.1:7687, only on this server)"
    exit 0
  fi
  sleep 3
done
echo "Neo4j did not come up: sudo docker logs pinpoint-neo4j" >&2
exit 1
