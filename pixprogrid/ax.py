"""Thin wrapper over the macOS Accessibility API — v1.1.0

Pixelmator Pro keeps its grid and background settings in a sandboxed
preferences file that only it may write. Writing that file from outside has no
effect on the running app: cfprefsd hands the app a cached copy, so an external
edit is ignored and can be overwritten later. Driving the Settings window
through the Accessibility API is the only way to change these settings in a
running Pixelmator Pro, so every write in this app goes through here.

AppleScript's System Events was tried first and rejected: it cannot commit a
text field (the value reverts as soon as the field redraws) and it cannot set a
colour well at all.
"""

import time

from ApplicationServices import (
    AXIsProcessTrustedWithOptions,
    AXUIElementCopyActionNames,
    AXUIElementCopyAttributeValue,
    AXUIElementCreateApplication,
    AXUIElementPerformAction,
    AXUIElementSetAttributeValue,
    AXValueGetValue,
    kAXTrustedCheckOptionPrompt,
    kAXValueCGPointType,
    kAXValueCGSizeType,
)

# Attribute and action names, spelled out so a typo is a NameError not a silent
# "attribute not found".
VALUE = "AXValue"
TITLE = "AXTitle"
ROLE = "AXRole"
CHILDREN = "AXChildren"
WINDOWS = "AXWindows"
POSITION = "AXPosition"
SIZE = "AXSize"
FOCUSED = "AXFocused"
DESCRIPTION = "AXDescription"
SELECTED = "AXSelected"

PRESS = "AXPress"
CONFIRM = "AXConfirm"


def is_trusted(prompt=False):
    """True when this process may drive other apps via Accessibility.

    With prompt=True macOS shows its "grant access in System Settings" alert.
    The answer never changes inside a single launch, so the app re-checks on a
    timer rather than assuming the first answer holds.
    """
    return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: prompt}))


def app_element(pid):
    return AXUIElementCreateApplication(pid)


def attr(element, name):
    """Attribute value, or None if the element has no such attribute."""
    if element is None:
        return None
    err, value = AXUIElementCopyAttributeValue(element, name, None)
    return value if err == 0 else None


def set_attr(element, name, value):
    """True when the write was accepted by the target app."""
    if element is None:
        return False
    return AXUIElementSetAttributeValue(element, name, value) == 0


def actions(element):
    if element is None:
        return []
    err, names = AXUIElementCopyActionNames(element, None)
    return list(names) if err == 0 else []


def perform(element, action=PRESS):
    if element is None:
        return False
    return AXUIElementPerformAction(element, action) == 0


def children(element):
    return list(attr(element, CHILDREN) or [])


def descendants(element, role=None, depth=6):
    """Every element below `element`, optionally filtered by AXRole.

    Depth-limited because a Settings pane is shallow and an unbounded walk over
    a document window is slow enough to be noticeable.
    """
    found = []
    if depth <= 0:
        return found
    for kid in children(element):
        if role is None or attr(kid, ROLE) == role:
            found.append(kid)
        found.extend(descendants(kid, role, depth - 1))
    return found


def point(element, name=POSITION):
    """(x, y) in screen coordinates, or None."""
    raw = attr(element, name)
    if raw is None:
        return None
    ok, value = AXValueGetValue(raw, kAXValueCGPointType, None)
    return (value.x, value.y) if ok else None


def extent(element):
    """(width, height), or None."""
    raw = attr(element, SIZE)
    if raw is None:
        return None
    ok, value = AXValueGetValue(raw, kAXValueCGSizeType, None)
    return (value.width, value.height) if ok else None


def top(element):
    """Y of the element's top edge, used to pair controls with their labels.

    The order of AXChildren is not the order the controls appear in — the
    Rulers pane returns "Gridline Every" and "Subdivisions" in either order and
    swaps them after an edit — so every control here is identified by where it
    sits, never by its index.
    """
    pos = point(element)
    return pos[1] if pos else 0.0


def window_named(app, title):
    for window in (attr(app, WINDOWS) or []):
        if attr(window, TITLE) == title:
            return window
    return None


def windows(app):
    return list(attr(app, WINDOWS) or [])


def press_menu_item(popup, item_title, timeout=3.0):
    """Open a pop-up button and choose the item with this title.

    Setting AXValue on a pop-up button does not change the selection, so the
    menu has to be opened and the item pressed.

    The menu appears asynchronously. Reading its children straight away gives
    nothing, and giving up at that point leaves the menu hanging open, which
    then breaks whatever is attempted next — so this waits for the menu to be
    populated, and always closes it again if the item is not there.
    """
    if not perform(popup, PRESS):
        return False

    menu = None
    deadline = time.time() + timeout
    while time.time() < deadline:
        menu = next((k for k in children(popup) if attr(k, ROLE) == "AXMenu"), None)
        if menu is not None and children(menu):
            break
        time.sleep(0.1)

    if menu is None or not children(menu):
        _dismiss_menu(popup, menu)
        return False

    for item in children(menu):
        if attr(item, TITLE) == item_title:
            pressed = perform(item, PRESS)
            time.sleep(0.2)  # let the menu close before anything else is read
            return pressed

    _dismiss_menu(popup, menu)
    return False


def _dismiss_menu(popup, menu):
    """Close an open pop-up menu without choosing anything."""
    if menu is not None and "AXCancel" in actions(menu):
        perform(menu, "AXCancel")
    else:
        perform(popup, PRESS)
    time.sleep(0.2)


def set_field(field, text):
    """Type a value into a text field and commit it.

    Setting AXValue alone only changes what is drawn: Pixelmator Pro's model
    keeps the old number and the field reverts on the next redraw. AXConfirm is
    what actually ends editing and applies the value.
    """
    set_attr(field, FOCUSED, True)
    if not set_attr(field, VALUE, str(text)):
        return False
    return perform(field, CONFIRM)
