#!/bin/zsh
# GPU jobs of the recognition benchmark, one at a time (so timings are not shared); logs in runs/logs/.
# Detectors and fine-tuning were dropped on 3 Nov (photo upload, not live camera); the small local VLMs stay as
# free alternatives to Claude. Run: nohup caffeinate -i ./queue.sh &
cd ${0:A:h}
PY=~/.venvs/pinpoint-vision/bin/python
run() { echo "$(date +%H:%M) start $*" >> runs/logs/queue.log
        "$@" > "runs/logs/$(echo $* | tr ' /:' '___' | cut -c1-80).log" 2>&1 \
          && echo "$(date +%H:%M) done  $*" >> runs/logs/queue.log \
          || echo "$(date +%H:%M) FAIL  $*" >> runs/logs/queue.log; }
for m in florence2-large qwen3vl-2b moondream2 qwen3vl-4b; do
  run $PY vlm_bench.py $m
done
echo "$(date +%H:%M) queue finished" >> runs/logs/queue.log
