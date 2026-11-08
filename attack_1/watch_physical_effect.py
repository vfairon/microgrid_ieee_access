"""
Live watcher for pandapower_outstation.py's real physical state -- shows
every bus voltage / line / transformer loading, not just the 5 points
exposed over DNP3. Run this in its own terminal on the same node as the
outstation (it reads /workspace/live_state.json, written by the outstation
after every command) *while* sending commands from the master elsewhere.

Usage: python3 watch_physical_effect.py
"""
import json
import time

STATE_FILE = "/workspace/live_state.json"
POLL_SECONDS = 1

prev = None
print("watching {} -- Ctrl-C to stop\n".format(STATE_FILE))

while True:
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        time.sleep(POLL_SECONDS)
        continue

    if state != prev:
        print("=== update ===")
        for section, values in state.items():
            print(section + ":")
            for name, value in values.items():
                flag = "  <-- BLACKED OUT (no voltage solution)" if value is None else ""
                print("  {:30s} {}{}".format(name, value, flag))
        print()
        prev = state

    time.sleep(POLL_SECONDS)
