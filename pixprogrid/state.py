"""The edited settings, and the snapshot that undoes them — v1.1.0

The snapshot is written to disk before anything is changed. If PixProGrid is
force-quit, crashes, or the Mac restarts while the edited settings are applied,
the next launch finds that file and puts Pixelmator Pro back — otherwise the
settings would be left changed with nothing on screen to say so.
"""

import json
import os

from AppKit import NSSearchPathForDirectoriesInDomains, NSApplicationSupportDirectory, NSUserDomainMask

# Light gray, #D3D3D3.
LIGHT_GRAY = [211 / 255.0, 211 / 255.0, 211 / 255.0, 1.0]

# Gridline every 100% with a single subdivision puts the only grid lines on the
# canvas edges, so the grid stays switched on — and the tools that need it keep
# working — but nothing is drawn across the image.
EDITED = {
    "ruler_units": "Percent",
    "grid_color": LIGHT_GRAY,
    "gridline_every": "100",
    "gridline_units": "Percent",
    "subdivisions": "1",
    "transparency_color": LIGHT_GRAY,
    "checkerboard": 0,
}

KEYS = tuple(EDITED)


def support_dir():
    root = NSSearchPathForDirectoriesInDomains(
        NSApplicationSupportDirectory, NSUserDomainMask, True
    )[0]
    path = os.path.join(root, "PixProGrid")
    os.makedirs(path, exist_ok=True)
    return path


def snapshot_path():
    return os.path.join(support_dir(), "snapshot.json")


def save_snapshot(state):
    """Record the settings to go back to. Written before anything changes."""
    path = snapshot_path()
    temp = path + ".tmp"
    with open(temp, "w") as handle:
        json.dump(state, handle, indent=2)
    os.replace(temp, path)


def load_snapshot():
    try:
        with open(snapshot_path()) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return None


def clear_snapshot():
    """Called once the settings are back to the user's own."""
    try:
        os.remove(snapshot_path())
    except OSError:
        pass


def same(a, b):
    """Compare one setting. Colours are lists of floats and never land exactly.

    The tolerance is a shade under 1/255: colours make the round trip through
    the Colors panel's 8-bit hex field, so a value that did not start life as
    8-bit sRGB comes back a fraction off and must still count as restored.
    """
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(abs(x - y) < 0.004 for x, y in zip(a, b))
    return str(a) == str(b)


def mismatches(actual, wanted):
    """The keys of `wanted` that `actual` does not match."""
    return [k for k in wanted if k in KEYS and not same(actual.get(k), wanted[k])]


def describe(state):
    """One-line summary, for the panel's status text and the log."""
    if not state:
        return "unknown"
    return "grid %s every %s%s, %s subdivision(s)" % (
        _hex(state.get("grid_color")),
        state.get("gridline_every"),
        "%" if state.get("gridline_units") == "Percent" else "",
        state.get("subdivisions"),
    )


def _hex(rgba):
    if not rgba:
        return "?"
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(c * 255))) for c in rgba[:3])
