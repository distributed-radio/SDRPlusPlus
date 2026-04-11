#!/usr/bin/env python3
"""
X411 LO retune prototype.

Tests two retune strategies while streaming:
  1. Hot retune (set_rx_freq while streaming) — check for sample glitches
  2. Stop/restart around PLL retune — measure gap duration

Run after: source /opt/uhd-x411/setup_env.sh

TODO: feed results into planning decision for x411_source tune() handler.
      If hot retune produces acceptable artefacts, approach B is viable.
      If not, confirm approach A (stop/restart).
"""

import sys, time, numpy as np

import importlib.util
if importlib.util.find_spec("uhd") is None:
    print("ERROR: uhd module not found. Did you source /opt/uhd-x411/setup_env.sh?")
    sys.exit(1)

import uhd

DEVICE_ARGS = (
    "mgmt_addr=192.168.7.162,"
    "addr=192.168.200.2,"
    "type=x4xx,"
    "num_recv_frames=2048,"
    "recv_buff_size=33554432"
)

RATE      = 30.72e6   # Msps — confirmed zero-overrun rate
FREQ_A    = 2140e6    # Band 1 DL centre
FREQ_B    = 920e6     # Band 8 DL centre — >128.75 MHz away, forces PLL retune
NCO_FREQ  = 2150e6    # Within ±128.75 MHz of FREQ_A — NCO-only retune
CAPTURE   = 0.05      # 50ms capture window per test
N_SAMPLES = int(RATE * CAPTURE)

def connect():
    print(f"Connecting: {DEVICE_ARGS}")
    usrp = uhd.usrp.MultiUSRP(DEVICE_ARGS)
    usrp.set_rx_rate(RATE, 0)
    usrp.set_clock_source("internal")
    return usrp

def make_streamer(usrp):
    sa = uhd.usrp.StreamArgs("fc32", "sc16")
    sa.channels = [0]
    st = usrp.get_rx_stream(sa)
    return st

def capture(streamer, n):
    """Capture n samples, return as complex64 array."""
    buf = np.zeros(n, dtype=np.complex64)
    md = uhd.types.RXMetadata()
    got = 0
    while got < n:
        chunk = min(n - got, 10000)
        rx = streamer.recv(buf[got:got+chunk], md, timeout=5.0)
        got += rx
    return buf

def rms_db(samples):
    p = np.mean(np.abs(samples)**2)
    return 10 * np.log10(p) if p > 0 else -np.inf

def tune_nco_only(usrp, freq, current_lo):
    """Retune using DSP/NCO only — RF LO stays fixed."""
    tr = uhd.types.TuneRequest(freq)
    tr.rf_freq        = current_lo
    tr.rf_freq_policy = uhd.types.TuneRequestPolicy.manual
    tr.dsp_freq_policy = uhd.types.TuneRequestPolicy.auto
    result = usrp.set_rx_freq(tr, 0)
    return result.actual_rf_freq

def tune_full(usrp, freq):
    """Full retune — PLL + NCO."""
    tr = uhd.types.TuneRequest(freq)
    result = usrp.set_rx_freq(tr, 0)
    return result.actual_rf_freq

# ── TEST 1: NCO-only retune (should be instant, no gap) ──────────────────────
print("\n=== TEST 1: NCO-only retune (within ±128.75 MHz) ===")
usrp = connect()
lo = tune_full(usrp, FREQ_A)
print(f"Initial LO: {lo/1e6:.3f} MHz")
streamer = make_streamer(usrp)
cmd = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)
cmd.stream_now = True
streamer.issue_stream_cmd(cmd)

pre = capture(streamer, N_SAMPLES)
t0 = time.monotonic()
new_lo = tune_nco_only(usrp, NCO_FREQ, lo)
elapsed_nco = time.monotonic() - t0
post = capture(streamer, N_SAMPLES)

streamer.issue_stream_cmd(uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont))
del streamer, usrp

print(f"NCO retune time:  {elapsed_nco*1000:.1f} ms")
print(f"Pre-retune RMS:   {rms_db(pre):.1f} dBFS")
print(f"Post-retune RMS:  {rms_db(post):.1f} dBFS")
print(f"New actual LO:    {new_lo/1e6:.3f} MHz  (expected unchanged: {FREQ_A/1e6:.3f})")

# ── TEST 2: Hot PLL retune (no stop/restart) ─────────────────────────────────
print("\n=== TEST 2: Hot PLL retune (>128.75 MHz jump, no stop/restart) ===")
usrp = connect()
lo = tune_full(usrp, FREQ_A)
streamer = make_streamer(usrp)
cmd = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)
cmd.stream_now = True
streamer.issue_stream_cmd(cmd)

pre = capture(streamer, N_SAMPLES)
t0 = time.monotonic()
new_lo = tune_full(usrp, FREQ_B)
elapsed_hot = time.monotonic() - t0
post = capture(streamer, N_SAMPLES)

streamer.issue_stream_cmd(uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont))
del streamer, usrp

print(f"Hot PLL retune time: {elapsed_hot*1000:.1f} ms")
print(f"Pre-retune RMS:      {rms_db(pre):.1f} dBFS")
print(f"Post-retune RMS:     {rms_db(post):.1f} dBFS")
print(f"New actual LO:       {new_lo/1e6:.3f} MHz")

# ── TEST 3: Stop/restart around PLL retune ────────────────────────────────────
print("\n=== TEST 3: Stop/restart around PLL retune ===")
usrp = connect()
lo = tune_full(usrp, FREQ_A)
streamer = make_streamer(usrp)
cmd = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)
cmd.stream_now = True
streamer.issue_stream_cmd(cmd)
_ = capture(streamer, N_SAMPLES)  # discard startup

t0 = time.monotonic()
streamer.issue_stream_cmd(uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont))
new_lo = tune_full(usrp, FREQ_B)
del streamer
streamer = make_streamer(usrp)
cmd2 = uhd.types.StreamCMD(uhd.types.StreamMode.start_cont)
cmd2.stream_now = True
streamer.issue_stream_cmd(cmd2)
post = capture(streamer, N_SAMPLES)
elapsed_restart = time.monotonic() - t0

streamer.issue_stream_cmd(uhd.types.StreamCMD(uhd.types.StreamMode.stop_cont))
del streamer, usrp

print(f"Stop/retune/start time: {elapsed_restart*1000:.1f} ms")
print(f"Post-retune RMS:        {rms_db(post):.1f} dBFS")
print(f"New actual LO:          {new_lo/1e6:.3f} MHz")

print("\n=== Summary ===")
print(f"NCO-only retune:        {elapsed_nco*1000:.1f} ms  (expected: <1 ms)")
print(f"Hot PLL retune:         {elapsed_hot*1000:.1f} ms  (check for artefacts)")
print(f"Stop/restart PLL:       {elapsed_restart*1000:.1f} ms  (expected: ~100-200 ms)")
print("\nConclusion: if hot PLL retune RMS post matches pre, approach B is viable.")
print("Otherwise use approach A (stop/restart) for clean samples after large hops.")
