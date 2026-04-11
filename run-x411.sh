#!/usr/bin/env bash
# Launch SDR++ with X411 source, then apply RT scheduling priority.
# Runs sdrpp as the current user (required for PulseAudio + X11 over XRDP).
set -e
cd "$(dirname "$0")"

ROOT="${1:-/tmp/sdrpp_x411_test}"

./build-x411/sdrpp --root "$ROOT" &
SDRPP_PID=$!

sleep 2
sudo chrt -f -p 50 "$SDRPP_PID"

echo "SDR++ PID $SDRPP_PID running at SCHED_FIFO priority 50"
wait "$SDRPP_PID"
