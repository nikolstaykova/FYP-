#!/bin/zsh
# Start the parts lab (see server.py). Add --lan to open it from a phone on the same Wi-Fi.
HERE=${0:A:h}
exec $HERE/../../../.venv-research/bin/python $HERE/server.py "$@"
