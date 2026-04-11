#!/usr/bin/env python3
"""
X411 capability probe.

Exhaustively interrogates UHD for device info, sensors, gain ranges,
frequency ranges, bandwidth ranges, antennas, clock sources, and time sources.

Helps determine which UHD APIs return useful data vs. zeros/stubs for the X411,
so the x411_source C++ module can call the right APIs and ignore the rest.

Run after: source /opt/uhd-x411/setup_env.sh
"""

import sys, pprint
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

SUBDEVS = ["A:0", "A:1", "B:0", "B:1"]

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def subsection(title):
    print(f"\n  --- {title} ---")

def try_call(label, fn, *args, **kwargs):
    """Call fn(*args), print result or exception."""
    try:
        result = fn(*args, **kwargs)
        print(f"  {label}: {result}")
        return result
    except Exception as e:
        print(f"  {label}: ERROR — {e}")
        return None

# ── Connect ───────────────────────────────────────────────────────────────────
section("Connection")
print(f"Args: {DEVICE_ARGS}")
try:
    usrp = uhd.usrp.MultiUSRP(DEVICE_ARGS)
    print("Connected OK")
except Exception as e:
    print(f"FATAL: {e}")
    sys.exit(1)

# ── Device discovery simulation ───────────────────────────────────────────────
section("Device Discovery (uhd.find_devices)")
hint = uhd.libpyuhd.types.device_addr("mgmt_addr=192.168.7.162")
try:
    found = uhd.find_devices(hint)
    print(f"  Found {len(found)} device(s):")
    for i, d in enumerate(found):
        print(f"  [{i}]:")
        for k in d.keys():
            print(f"      {k} = {d[k]}")
except Exception as e:
    print(f"  uhd.find_devices: ERROR — {e}")

# Try alternate API
try:
    found2 = uhd.libpyuhd.types.device.find(hint)
    print(f"\n  device.find() found {len(found2)} device(s):")
    for i, d in enumerate(found2):
        print(f"  [{i}]:")
        for k in d.keys():
            print(f"      {k} = {d[k]}")
except Exception as e:
    print(f"  device.find(): ERROR — {e}")

# ── Motherboard info ──────────────────────────────────────────────────────────
section("Motherboard Info")
try_call("MCR (Hz)",         usrp.get_master_clock_rate)
try_call("Num mboards",      usrp.get_num_mboards)
try_call("Mboard name",      usrp.get_mboard_name, 0)
try_call("RX info ch0",      usrp.get_usrp_rx_info, 0)

subsection("PP (property tree) — mboard sensors")
try:
    sensors = usrp.get_mboard_sensor_names(0)
    print(f"  Sensor names: {sensors}")
    for s in sensors:
        try:
            val = usrp.get_mboard_sensor(s, 0)
            print(f"    {s}: {val}")
        except Exception as e:
            print(f"    {s}: ERROR — {e}")
except Exception as e:
    print(f"  get_mboard_sensor_names: ERROR — {e}")

subsection("Clock sources")
try_call("get_clock_sources(0)", usrp.get_clock_sources, 0)
try_call("get_clock_source(0)",  usrp.get_clock_source, 0)

subsection("Time sources")
try_call("get_time_sources(0)", usrp.get_time_sources, 0)
try_call("get_time_source(0)",  usrp.get_time_source, 0)

# ── Per-channel capability ────────────────────────────────────────────────────
for subdev in SUBDEVS:
    section(f"Channel subdev={subdev}")

    # Set subdev spec to get accurate per-channel info
    try:
        usrp.set_rx_subdev_spec(uhd.libpyuhd.usrp.subdev_spec(subdev), 0)
        print(f"  set_rx_subdev_spec({subdev!r}) OK")
    except Exception as e:
        print(f"  set_rx_subdev_spec({subdev!r}): ERROR — {e}")
        continue

    ch = 0  # After setting subdev spec, logical channel 0 = this subdev

    subsection("Subdev info")
    try_call("get_rx_subdev_name(0)",  usrp.get_rx_subdev_name, ch)
    try_call("get_rx_subdev_spec(0)",  usrp.get_rx_subdev_spec, 0)
    try_call("get_rx_num_channels()",  usrp.get_rx_num_channels)

    subsection("Frequency range")
    try:
        fr = usrp.get_rx_freq_range(ch)
        print(f"  get_rx_freq_range: start={fr.start()/1e6:.3f} stop={fr.stop()/1e6:.3f} step={fr.step()/1e6:.6f} MHz")
    except Exception as e:
        print(f"  get_rx_freq_range: ERROR — {e}")

    try_call("get_rx_freq(0)",         usrp.get_rx_freq, ch)

    # Set a test frequency and check actual
    try:
        TEST_FREQ = 2140e6
        tr = uhd.types.TuneRequest(TEST_FREQ)
        result = usrp.set_rx_freq(tr, ch)
        print(f"  set_rx_freq({TEST_FREQ/1e6:.1f} MHz):")
        print(f"    target_rf_freq  = {result.target_rf_freq/1e6:.4f} MHz")
        print(f"    actual_rf_freq  = {result.actual_rf_freq/1e6:.4f} MHz")
        print(f"    target_dsp_freq = {result.target_dsp_freq/1e6:.4f} MHz")
        print(f"    actual_dsp_freq = {result.actual_dsp_freq/1e6:.4f} MHz")
    except Exception as e:
        print(f"  set_rx_freq test: ERROR — {e}")

    subsection("Sample rates")
    try:
        rates = usrp.get_rx_rates(ch)
        print(f"  get_rx_rates: {len(rates)} range(s):")
        for r in rates:
            print(f"    start={r.start()/1e6:.4f} stop={r.stop()/1e6:.4f} step={r.step()/1e6:.6f} MHz")
    except Exception as e:
        print(f"  get_rx_rates: ERROR — {e}")

    subsection("Bandwidth")
    try:
        bw = usrp.get_rx_bandwidth_range(ch)
        print(f"  get_rx_bandwidth_range: {len(bw)} range(s):")
        for r in bw:
            print(f"    start={r.start()/1e6:.4f} stop={r.stop()/1e6:.4f} step={r.step()/1e6:.6f} MHz")
    except Exception as e:
        print(f"  get_rx_bandwidth_range: ERROR — {e}")

    try_call("get_rx_bandwidth(0)",    usrp.get_rx_bandwidth, ch)

    subsection("Gain")
    try:
        gr = usrp.get_rx_gain_range(ch)
        print(f"  get_rx_gain_range: start={gr.start()} stop={gr.stop()} step={gr.step()}")
    except Exception as e:
        print(f"  get_rx_gain_range: ERROR — {e}")

    try_call("get_rx_gain(0)",         usrp.get_rx_gain, ch)

    try:
        gain_names = usrp.get_rx_gain_names(ch)
        print(f"  get_rx_gain_names: {gain_names}")
        for gn in gain_names:
            try:
                gr = usrp.get_rx_gain_range(gn, ch)
                print(f"    '{gn}': start={gr.start()} stop={gr.stop()} step={gr.step()}")
            except Exception as e:
                print(f"    '{gn}': ERROR — {e}")
    except Exception as e:
        print(f"  get_rx_gain_names: ERROR — {e}")

    subsection("AGC")
    try:
        agc = usrp.get_rx_agc_supported(ch)
        print(f"  get_rx_agc_supported: {agc}")
    except Exception as e:
        print(f"  get_rx_agc_supported: ERROR — {e}")

    subsection("Antennas")
    try:
        ants = usrp.get_rx_antennas(ch)
        print(f"  get_rx_antennas: {ants}")
    except Exception as e:
        print(f"  get_rx_antennas: ERROR — {e}")

    try_call("get_rx_antenna(0)",      usrp.get_rx_antenna, ch)

    subsection("RX sensors")
    try:
        snames = usrp.get_rx_sensor_names(ch)
        print(f"  get_rx_sensor_names: {snames}")
        for s in snames:
            try:
                val = usrp.get_rx_sensor(s, ch)
                print(f"    {s}: {val}")
            except Exception as e:
                print(f"    {s}: ERROR — {e}")
    except Exception as e:
        print(f"  get_rx_sensor_names: ERROR — {e}")

    subsection("LO sources")
    try:
        lo_names = usrp.get_rx_lo_names(ch)
        print(f"  get_rx_lo_names: {lo_names}")
        for lo in lo_names:
            try:
                sources = usrp.get_rx_lo_sources(lo, ch)
                print(f"    '{lo}' sources: {sources}")
            except Exception as e:
                print(f"    '{lo}' sources: ERROR — {e}")
            try:
                src = usrp.get_rx_lo_source(lo, ch)
                print(f"    '{lo}' current source: {src}")
            except Exception as e:
                print(f"    '{lo}' current source: ERROR — {e}")
            try:
                lr = usrp.get_rx_lo_freq_range(lo, ch)
                print(f"    '{lo}' freq range: {lr.start()/1e6:.1f}–{lr.stop()/1e6:.1f} MHz")
            except Exception as e:
                print(f"    '{lo}' freq range: ERROR — {e}")
    except Exception as e:
        print(f"  get_rx_lo_names: ERROR — {e}")

print(f"\n{'='*60}")
print("  Done")
print(f"{'='*60}\n")
