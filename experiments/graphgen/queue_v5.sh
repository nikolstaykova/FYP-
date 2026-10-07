#!/bin/bash
# Runs after v3/v4: finish v4 electronics (rerun any failed tutorial), then v5 electronics; v5 LEGO after v4 LEGO.
cd /Users/nikolstaykova/Desktop/fyp
PY=.venv-research/bin/python
busy() { pgrep -f "graphgen.run --domain $1 --route subscription --version $2" >/dev/null; }
(
  while busy arduino v4; do sleep 60; done
  E4=$(ls -d experiments/graphgen/*arduino-sonnet-high-seeded-v4 | tail -1)
  caffeinate -i $PY -m graphgen.run --domain arduino --route subscription --version v4 --repair-rounds 2 --workers 3 --replay "$E4" > experiments/graphgen/arduino-v4-finish.log 2>&1
  caffeinate -i $PY -m graphgen.run --domain arduino --route subscription --version v5 --repair-rounds 2 --workers 3 > experiments/graphgen/arduino-v5-full.log 2>&1
) &
(
  sleep 120
  while busy lego v3 || pgrep -f "lego-v3-full.pid" >/dev/null || busy lego v4; do sleep 60; done
  caffeinate -i $PY -m graphgen.run --domain lego --route subscription --version v5 --repair-rounds 2 --workers 4 > experiments/graphgen/lego-v5-full.log 2>&1
) &
wait
