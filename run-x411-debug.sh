#!/usr/bin/env bash
# Launch SDR++ under gdb to capture crash backtrace.
# Run this from your XRDP terminal when debugging crashes.
cd "$(dirname "$0")"

ROOT="${1:-/tmp/sdrpp_x411_test}"
CORE=/tmp/sdrpp_core_$$

# Bypass apport and write core dump directly
ulimit -c unlimited
sudo sysctl -q kernel.core_pattern="/tmp/core.%e.%p" 2>/dev/null || true

echo "Starting SDR++ under gdb. Reproduce the crash, then the backtrace will print."
echo "GDB output is mirrored to /tmp/sdrpp_crash.log"
echo ""

gdb \
    -ex "set pagination off" \
    -ex "set confirm off" \
    -ex "set logging file /tmp/sdrpp_crash.log" \
    -ex "set logging overwrite on" \
    -ex "set logging enabled on" \
    -ex "handle SIGPIPE nostop noprint" \
    -ex "handle SIGHUP nostop noprint" \
    -ex "catch signal SIGSEGV" \
    -ex "catch signal SIGABRT" \
    -ex "run --root $ROOT" \
    -ex "echo \n=== SIGNAL CAUGHT ===\n" \
    -ex "backtrace 50" \
    -ex "echo \n=== THREAD LIST ===\n" \
    -ex "info threads" \
    -ex "echo \n=== FRAME 0 LOCALS ===\n" \
    -ex "info locals" \
    -ex "set logging enabled off" \
    -ex "quit" \
    ./build-x411/sdrpp

echo ""
echo "=== Backtrace saved to /tmp/sdrpp_crash.log ==="
grep -A 60 "SIGNAL CAUGHT" /tmp/sdrpp_crash.log 2>/dev/null || echo "No backtrace captured"
