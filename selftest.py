"""Headless check of the Pixelmator Pro driver — v1.0.0

    ./venv/bin/python selftest.py read      show the current settings
    ./venv/bin/python selftest.py apply     snapshot, then apply the edited settings
    ./venv/bin/python selftest.py restore   put the snapshot back
    ./venv/bin/python selftest.py roundtrip apply, verify, restore, verify

Run this rather than the app when changing axdriver behaviour: it exercises the
same code paths without a window in the way.
"""

import json
import sys

from pixprogrid import ax, state
from pixprogrid.pixelmator import Settings, PixelmatorError


def show(label, value):
    print("%-10s %s" % (label, json.dumps(value, indent=2, sort_keys=True)))


def main(argv):
    command = argv[1] if len(argv) > 1 else "read"

    if not ax.is_trusted(prompt=True):
        sys.exit(
            "Accessibility access is not granted for this process.\n"
            "System Settings > Privacy & Security > Accessibility."
        )

    if command == "read":
        with Settings() as settings:
            show("current", settings.read())

    elif command == "apply":
        with Settings() as settings:
            before = settings.read()
            state.save_snapshot(before)
            show("saved", before)
            settings.write(state.EDITED)
            show("now", settings.read())

    elif command == "restore":
        snapshot = state.load_snapshot()
        if not snapshot:
            sys.exit("No snapshot to restore.")
        with Settings() as settings:
            settings.write(snapshot)
            show("now", settings.read())
        state.clear_snapshot()

    elif command == "roundtrip":
        with Settings() as settings:
            before = settings.read()
            show("before", before)
            settings.write(state.EDITED)
            applied = settings.read()
            show("applied", applied)
            bad = [k for k in state.KEYS if not _same(applied.get(k), state.EDITED[k])]
            print("apply mismatches:", bad or "none")

            settings.write(before)
            after = settings.read()
            show("after", after)
            bad = [k for k in state.KEYS if not _same(after.get(k), before.get(k))]
            print("restore mismatches:", bad or "none")

    else:
        sys.exit(__doc__)


def _same(a, b):
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(abs(x - y) < 0.004 for x, y in zip(a, b))
    return str(a) == str(b)


if __name__ == "__main__":
    try:
        main(sys.argv)
    except PixelmatorError as error:
        sys.exit("error: %s" % error)
