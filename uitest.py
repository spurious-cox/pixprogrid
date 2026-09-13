"""End-to-end check of the panel — v1.0.0

    ./venv/bin/python uitest.py <pid-of-a-running-PixProGrid>

Presses the app's own switch through the Accessibility API, then reads
Pixelmator Pro back to confirm the edited settings landed; presses it again and
confirms the user's settings returned. This is the wiring that selftest.py does
not cover.
"""

import sys
import time

from pixprogrid import ax, state
from pixprogrid.pixelmator import Settings


def find_switch(pid):
    app = ax.app_element(int(pid))
    for window in ax.windows(app):
        if ax.attr(window, ax.TITLE) != "PixPro Grid":
            continue
        # An NSSwitch surfaces as an untitled AXButton carrying a 0/1 value;
        # every other button in the panel has a title or no value at all.
        for kid in ax.descendants(window, "AXButton"):
            if ax.attr(kid, ax.TITLE) is None and isinstance(ax.attr(kid, ax.VALUE), int):
                return kid
    return None


def read_pixelmator():
    with Settings() as settings:
        return settings.read()


def same(a, b):
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(abs(x - y) < 0.004 for x, y in zip(a, b))
    return str(a) == str(b)


def main():
    pid = sys.argv[1]
    switch = find_switch(pid)
    if switch is None:
        sys.exit("No PixPro Grid switch found for pid %s" % pid)
    print("switch role:", ax.attr(switch, ax.ROLE), "value:", ax.attr(switch, ax.VALUE))

    before = read_pixelmator()
    print("before:", state.describe(before))

    print("-> switching on")
    ax.perform(switch)
    time.sleep(14)
    applied = read_pixelmator()
    print("applied:", state.describe(applied))
    bad = [k for k in state.KEYS if not same(applied.get(k), state.EDITED[k])]
    print("apply mismatches:", bad or "none")

    print("-> switching off")
    ax.perform(switch)
    time.sleep(14)
    after = read_pixelmator()
    print("after:", state.describe(after))
    bad = [k for k in state.KEYS if not same(after.get(k), before.get(k))]
    print("restore mismatches:", bad or "none")
    print("snapshot left behind:", state.load_snapshot() is not None)


if __name__ == "__main__":
    main()
