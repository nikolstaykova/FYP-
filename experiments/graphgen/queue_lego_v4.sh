#!/bin/bash
cd /Users/nikolstaykova/Desktop/fyp
sleep 20
while kill -0 $(cat experiments/graphgen/lego-v3-full.pid) 2>/dev/null; do sleep 60; done
exec caffeinate -i .venv-research/bin/python -m graphgen.run --domain lego --route subscription --version v4 --repair-rounds 2 --workers 4 --replay experiments/graphgen/20261005-020834-lego-sonnet-high-empty-v4
