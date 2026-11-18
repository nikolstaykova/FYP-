# Neo4j on our own server

Pinpoint's lessons and parts live in Neo4j 5 Community Edition on a Hetzner Cloud server (CX23, Nuremberg),
since 18 November 2026. Why and how it was chosen: RESEARCH.md R30; the design: DATA_STRUCTURE.md §10.5.

- The database listens only on the server itself; the firewall lets in SSH only.
- The Mac reaches it through an SSH tunnel, so `.env` has `NEO4J_URI=bolt://localhost:7687`.
- `.env` (not in git) holds `PINPOINT_DB_HOST=root@<server ip>` and the Neo4j user and password.

## Every day

```bash
research/recognition/lab/run.sh --lan --https   # opens the tunnel itself, then starts the app server
deploy/neo4j/tunnel.sh stop                      # close the tunnel
./pinpoint db stats                              # what is in the database
./pinpoint db check                              # the database against the files
```

The Neo4j browser: with the tunnel up, http://localhost:7474 (user `neo4j`, the password from `.env`).

## Setting it up again (a new server)

1. A Linux server (Ubuntu) with the public key `~/.ssh/pinpoint_db.pub` and a firewall that allows SSH only.
2. `scp -i ~/.ssh/pinpoint_db deploy/neo4j/setup.sh root@<ip>:` then
   `ssh -i ~/.ssh/pinpoint_db root@<ip> "NEO4J_PASSWORD='<new password>' bash setup.sh"`
3. In `.env`: `PINPOINT_DB_HOST=root@<ip>`, `NEO4J_URI=bolt://localhost:7687`, `NEO4J_USERNAME=neo4j`,
   `NEO4J_PASSWORD=<new password>`, `NEO4J_DATABASE=neo4j`.
4. `deploy/neo4j/tunnel.sh`, then `./pinpoint db load` (about 2.5 minutes) and `./pinpoint db check`.

Nothing is lost if the server goes: the files in the repo are the source, and `db load` rebuilds the database.

## On the server

```bash
ssh -i ~/.ssh/pinpoint_db root@<ip>
docker ps                      # pinpoint-neo4j should be Up
docker logs --tail 50 pinpoint-neo4j
docker restart pinpoint-neo4j
```
