#!/bin/zsh
# One lesson through its route's WHOLE flow, as the batch and repeat tests run it, every Claude call on one model:
#   run_flow.sh <route: booklet|lego3d|arduino> <case: set id or link> <model> <run dir>
# booklet: lego_booklet.pdf_lesson (reads, repairs, registers in the store, READY check)
# lego3d:  lessons lego, then lesson_store build lego
# arduino: lessons electronics, then lesson_store build arduino
# then the store is validated. Everything is written under <run dir>: lessons/ (LESSON_OUT), store/ (LESSON_STORE, a
# copy of the real store taken first), flow.log, validate.txt, rc. PINPOINT_MODEL makes every call use <model>.
route=$1; c=$2; model=$3; D=${4:?run dir}
cd /Users/nikolstaykova/Desktop/fyp
PY=.venv-research/bin/python
mkdir -p $D/lessons
cp -cR data/lessons/store $D/store 2>/dev/null || cp -R data/lessons/store $D/store  # (APFS clone where it can)
export LESSON_OUT=$PWD/$D/lessons LESSON_STORE=$PWD/$D/store PINPOINT_MODEL=$model
[[ $D = /* ]] && export LESSON_OUT=$D/lessons LESSON_STORE=$D/store
log=$D/flow.log
case $route in
  booklet) ./pinpoint lego_booklet.pdf_lesson $c --model $model --repair-model $model > $log 2>&1; rc=$? ;;
  lego3d)  ./pinpoint lessons lego $c --model $model > $log 2>&1 && ./pinpoint lesson_store build lego $c >> $log 2>&1; rc=$? ;;
  arduino) id=$(PYTHONPATH=code $PY -c "from graph.arduino.circuit_lesson import slug; print(slug('$c'))")
           ./pinpoint lessons electronics $c --model $model > $log 2>&1 && ./pinpoint lesson_store build arduino $id >> $log 2>&1; rc=$? ;;
  *) echo "unknown route $route" > $log; rc=2 ;;
esac
./pinpoint lesson_store validate > $D/validate.txt 2>&1
echo $rc > $D/rc
exit 0
