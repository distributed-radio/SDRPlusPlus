#!/usr/bin/env python3
"""
X411 sample rate probe.

Queries get_rx_rates() and get_rx_bandwidth_range() for each channel,
then compares against the expected 245.76 MHz MCR divisor table.

Run after: source /opt/uhd-x411/setup_env.sh
"""

import subprocess, sys

# Ensure we use the patched UHD Python bindings
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

MCR = 245.76e6  # Fixed master clock rate
NCO_RANGE = 128.75e6  # Max DDC offset

# Expected valid rates (245.76 / 2^n, n=0..8, plus CIC decimations)
EXPECTED_RATES = [
    245.76e6,
    122.88e6,
     61.44e6,
     30.72e6,
     15.36e6,
      7.68e6,
      3.84e6,
      1.92e6,
      0.96e6,
]

CHANNELS = [
    (0, "A:0 (J4)"),
    (1, "A:1 (J3)"),
]

def check_divisor(rate):
    """Check if rate is an integer divisor of MCR."""
    if rate == 0:
        return False
    ratio = MCR / rate
    return abs(ratio - round(ratio)) < 1e-6

def main():
    print(f"Connecting to X411: {DEVICE_ARGS}\n")
    try:
        usrp = uhd.usrp.MultiUSRP(DEVICE_ARGS)
    except Exception as e:
        print(f"ERROR: Could not connect: {e}")
        sys.exit(1)

    info = usrp.get_usrp_rx_info(0)
    print(f"Device: {info.get('mboard_id', '?')}  serial={info.get('mboard_serial', '?')}")
    print(f"MCR reported: {usrp.get_master_clock_rate() / 1e6:.4f} MHz\n")

    for ch, label in CHANNELS:
        print(f"{'='*60}")
        print(f"Channel {ch} — {label}")
        print(f"{'='*60}")

        # --- Sample rates ---
        rate_ranges = usrp.get_rx_rates(ch)
        print(f"\nget_rx_rates() returned {len(rate_ranges)} range(s):")
        all_rates = []
        for r in rate_ranges:
            step = r.step() if r.step() > 0 else 100e3
            print(f"  start={r.start()/1e6:.4f} stop={r.stop()/1e6:.4f} step={step/1e6:.4f} MHz")
            f = r.start()
            while f <= r.stop() + 1:
                all_rates.append(f)
                if step == 0:
                    break
                f += step

        print(f"\n  Total enumerable rates: {len(all_rates)}")
        if len(all_rates) <= 50:
            for r in all_rates:
                ok = check_divisor(r)
                print(f"    {r/1e6:10.4f} Msps  {'✓ divisor' if ok else '✗ not integer divisor'}")
        else:
            print(f"  (too many to list — checking expected rates only)")

        print(f"\n  Expected valid rates vs reported ranges:")
        for er in EXPECTED_RATES:
            in_range = any(
                r.start() <= er <= r.stop()
                for r in rate_ranges
            )
            print(f"    {er/1e6:8.2f} Msps  {'IN RANGE' if in_range else 'NOT IN RANGE'}")

        # --- Bandwidth ---
        print(f"\nget_rx_bandwidth_range():")
        bw_ranges = usrp.get_rx_bandwidth_range(ch)
        for r in bw_ranges:
            step = r.step() if r.step() > 0 else 100e3
            print(f"  start={r.start()/1e6:.4f} stop={r.stop()/1e6:.4f} step={step/1e6:.4f} MHz")

        # --- Antennas ---
        ants = usrp.get_rx_antennas(ch)
        print(f"\nget_rx_antennas(): {ants}")

        # --- Clock sources ---
        clocks = usrp.get_clock_sources(0)
        print(f"\nget_clock_sources(): {clocks}")

        # --- Gain ---
        gain_range = usrp.get_rx_gain_range(ch)
        print(f"\nget_rx_gain_range(): start={gain_range.start()} stop={gain_range.stop()} step={gain_range.step()}")

        print()

    print("Done.")

if __name__ == "__main__":
    main()
