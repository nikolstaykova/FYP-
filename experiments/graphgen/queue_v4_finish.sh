#!/bin/bash
# After electronics v4 finishes: rerun its failed tutorials (a GitHub download timed out). v5 is paused.
cd /Users/nikolstaykova/Desktop/fyp
busy() { pgrep -f "graphgen.run --domain arduino --route subscription --version v4" >/dev/null; }
while busy; do sleep 60; done
E4=$(ls -d experiments/graphgen/*arduino-sonnet-high-seeded-v4 | tail -1)
exec caffeinate -i .venv-research/bin/python -m graphgen.run --domain arduino --route subscription --version v4 --repair-rounds 2 --workers 3 --replay "$E4"
