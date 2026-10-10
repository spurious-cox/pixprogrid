"""Reads and writes Pixelmator Pro's grid and background settings — v1.2.0

Everything here drives the real Settings window through the Accessibility API.
See ax.py for why nothing writes the preferences file directly.

Both installed builds are supported, and they are separate apps with separate
preference files:

    com.apple.pixelmator            Pixelmator Pro Creator Studio (4.3)
    com.pixelmatorteam.pixelmator.x Pixelmator Pro (3.8)

Controls are found by where they sit relative to their labels. Index order is
not stable — the Rulers pane hands back "Gridline Every" and "Subdivisions" in
either order, and swaps them after an edit — and the label text differs between
builds ("Transparency:" in 4.3, "Background:" in 3.8).
"""

import time

from AppKit import NSWorkspace, NSApplicationActivateIgnoringOtherApps

from . import ax

BUNDLE_IDS = ("com.apple.pixelmator", "com.pixelmatorteam.pixelmator.x")

PANES = ("General", "Editing", "Rulers", "Workspace")
COLORS_PANEL = "Colors"


def pane_name(title):
    """The pane a Settings window title stands for, or None.

    The window is titled after the selected pane, but not always with its
    toolbar label: Pixelmator Pro 3.8 titles the Workspace pane "Workspace
    Layout". A title that starts with a pane's name is that pane.
    """
    for name in PANES:
        if title == name or (title and str(title).startswith(name + " ")):
            return name
    return None

# Menu titles differ by build and macOS version.
SETTINGS_ITEMS = ("Settings…", "Preferences…")

# Labels that mark the transparency/background colour row in the General pane.
BACKGROUND_LABELS = ("Transparency:", "Background:")

# A label unique to each pane, used to confirm a pane switch has actually
# happened rather than trusting a timer.
PANE_MARKERS = {
    "Rulers": ("Ruler Units:",),
    "General": BACKGROUND_LABELS,
}

SETTLE = 0.35  # seconds to let a pane redraw before reading it back


class PixelmatorError(Exception):
    pass


def find_app():
    """The running Pixelmator Pro to drive.

    With both builds running the active one wins, so the app follows whichever
    Pixelmator the user is actually working in.
    """
    matches = [
        app
        for app in NSWorkspace.sharedWorkspace().runningApplications()
        if app.bundleIdentifier() in BUNDLE_IDS
    ]
    if not matches:
        raise PixelmatorError("No version of Pixelmator Pro is open. Open Pixelmator Pro first.")
    for app in matches:
        if app.isActive():
            return app
    return matches[0]


def _rgba(color_string):
    """Parse a colour well's AXValue, e.g. 'rgb 0.827451 0.827451 0.827451 1'."""
    if not color_string:
        return None
    parts = str(color_string).split()
    if len(parts) != 5 or parts[0] != "rgb":
        return None
    try:
        return [float(p) for p in parts[1:]]
    except ValueError:
        return None


def _hex(rgba):
    r, g, b = (max(0, min(255, round(c * 255))) for c in rgba[:3])
    return "%02X%02X%02X" % (r, g, b)


def _close(window):
    button = ax.attr(window, "AXCloseButton")
    if button is not None:
        ax.perform(button)


class Settings:
    """A short-lived session against one Pixelmator Pro's Settings window.

    Use it as a context manager: it opens the Settings window if it was closed,
    leaves the Colors panel as it found it, and restores the pane the user had
    selected.

        with Settings() as s:
            state = s.read()
            s.write(edited)
    """

    def __init__(self):
        self.app = find_app()
        self.bundle_id = self.app.bundleIdentifier()
        self.element = ax.app_element(self.app.processIdentifier())
        self._opened_settings = False
        self._original_pane = None
        self._colors_was_open = False
        self._color_mode = None

    # ---- lifecycle -----------------------------------------------------

    def __enter__(self):
        self.activate()
        self._colors_was_open = self._colors_panel() is not None
        window = self._settings_window()
        if window is None:
            self._open_settings()
            self._opened_settings = True
            # Pixelmator Pro builds the Settings window lazily, and the first
            # open after launch is much slower than later ones.
            for _ in range(40):
                window = self._settings_window()
                if window is not None:
                    break
                time.sleep(0.15)
            if window is None:
                raise PixelmatorError("Could not open Pixelmator Pro's Settings window.")
        self._original_pane = pane_name(ax.attr(window, ax.TITLE))
        return self

    def __exit__(self, exc_type, exc, tb):
        panel = self._colors_panel()
        if panel is not None:
            if self._color_mode is not None:
                self._restore_color_mode(panel)
            if not self._colors_was_open:
                _close(panel)
        window = self._settings_window()
        if window is not None:
            if self._opened_settings:
                _close(window)
            elif self._original_pane:
                self.select_pane(self._original_pane)
        return False

    def activate(self):
        """Bring Pixelmator Pro forward.

        The Colors panel hides the moment Pixelmator stops being the active
        app, so it has to be frontmost for the whole colour-setting sequence.
        """
        if not self.app.isActive():
            self.app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
            time.sleep(0.4)

    # ---- window plumbing -----------------------------------------------

    def _settings_window(self):
        """The Settings window, whose title is the name of the selected pane."""
        for window in ax.windows(self.element):
            if pane_name(ax.attr(window, ax.TITLE)):
                return window
        return None

    def _colors_panel(self):
        return ax.window_named(self.element, COLORS_PANEL)

    def _open_settings(self):
        menu_bar = ax.attr(self.element, "AXMenuBar")
        # The app menu is the one after the Apple menu.
        items = ax.children(menu_bar)
        if len(items) < 2:
            raise PixelmatorError("Pixelmator Pro's menu bar is not available.")
        app_menu_item = items[1]
        ax.perform(app_menu_item)
        menu = None
        for _ in range(20):
            time.sleep(0.15)
            menu = next(
                (k for k in ax.children(app_menu_item) if ax.attr(k, ax.ROLE) == "AXMenu"), None
            )
            if menu is not None and ax.children(menu):
                break
        if menu is None:
            raise PixelmatorError("Pixelmator Pro's application menu did not open.")
        for item in ax.children(menu):
            if ax.attr(item, ax.TITLE) in SETTINGS_ITEMS:
                ax.perform(item)
                return
        ax.perform(app_menu_item)  # close the menu we opened
        raise PixelmatorError("No Settings item in Pixelmator Pro's application menu.")

    def select_pane(self, name):
        """Show a Settings pane and return its group, once it is really there.

        Pressing the toolbar button and waiting a fixed interval is not enough:
        the pane swaps asynchronously, so the group that comes back can still
        be the previous pane's. That went unnoticed because the next thing to
        happen was usually a lookup that failed loudly — but when it did not,
        a control from the wrong pane got driven. This waits for both the
        window title and a label that only this pane has.
        """
        window = self._settings_window()
        if window is None:
            raise PixelmatorError("Pixelmator Pro's Settings window closed unexpectedly.")

        if pane_name(ax.attr(window, ax.TITLE)) != name:
            toolbar = next(
                (k for k in ax.children(window) if ax.attr(k, ax.ROLE) == "AXToolbar"), None
            )
            if toolbar is None:
                raise PixelmatorError("Pixelmator Pro's Settings toolbar is not available.")
            button = next(
                (b for b in ax.children(toolbar) if ax.attr(b, ax.TITLE) == name), None
            )
            if button is None:
                raise PixelmatorError("No %s pane in Pixelmator Pro's Settings." % name)
            ax.perform(button)

        marker = PANE_MARKERS.get(name, ())
        for _ in range(40):
            window = self._settings_window()
            if window is not None and pane_name(ax.attr(window, ax.TITLE)) == name:
                group = next(
                    (k for k in ax.children(window) if ax.attr(k, ax.ROLE) == "AXGroup"), None
                )
                if group is not None and (
                    not marker or self._label_top(group, marker) is not None
                ):
                    return group
            time.sleep(0.15)
        raise PixelmatorError("Pixelmator Pro's %s pane did not open." % name)

    @staticmethod
    def _pane_group(window):
        group = next((k for k in ax.children(window) if ax.attr(k, ax.ROLE) == "AXGroup"), None)
        if group is None:
            raise PixelmatorError("Pixelmator Pro's Settings pane is empty.")
        return group

    # ---- control lookup -------------------------------------------------

    @staticmethod
    def _label_top(group, texts):
        """Y of the first static text whose value matches one of `texts`."""
        for kid in ax.children(group):
            if ax.attr(kid, ax.ROLE) == "AXStaticText" and ax.attr(kid, ax.VALUE) in texts:
                return ax.top(kid)
        return None

    @staticmethod
    def _nearest(group, role, y, limit=14.0):
        """The control of this role whose top edge is closest to y.

        Rows line up to within a couple of points; the limit keeps a missing
        control from silently matching the row above or below.
        """
        best, best_gap = None, limit
        for kid in ax.children(group):
            if ax.attr(kid, ax.ROLE) != role:
                continue
            gap = abs(ax.top(kid) - y)
            if gap <= best_gap:
                best, best_gap = kid, gap
        return best

    def _rulers_controls(self, group):
        """The five Rulers-pane controls this app touches, keyed by name."""
        rows = {
            "ruler_units": (self._label_top(group, ("Ruler Units:",)), "AXPopUpButton"),
            "grid_color": (self._label_top(group, ("Grid:",)), "AXColorWell"),
            "gridline_every": (self._label_top(group, ("Gridline Every:",)), "AXTextField"),
            "gridline_units": (self._label_top(group, ("Gridline Every:",)), "AXPopUpButton"),
            "subdivisions": (self._label_top(group, ("Subdivisions:",)), "AXTextField"),
        }
        found = {}
        for name, (y, role) in rows.items():
            if y is None:
                raise PixelmatorError("Could not find the %s row in the Rulers pane." % name)
            control = self._nearest(group, role, y)
            if control is None:
                raise PixelmatorError("Could not find the %s control in the Rulers pane." % name)
            found[name] = control
        return found

    def _general_controls(self, group):
        y = self._label_top(group, BACKGROUND_LABELS)
        if y is None:
            raise PixelmatorError("Could not find the background row in the General pane.")
        well = self._nearest(group, "AXColorWell", y)
        checkbox = None
        for kid in ax.children(group):
            if ax.attr(kid, ax.ROLE) == "AXCheckBox" and ax.attr(kid, ax.TITLE) == "Checkerboard":
                checkbox = kid
        if well is None or checkbox is None:
            raise PixelmatorError("Could not find the background controls in the General pane.")
        return {"transparency_color": well, "checkerboard": checkbox}

    # ---- reading ---------------------------------------------------------

    def read(self):
        """Every setting this app changes, as a plain dict safe to store."""
        state = {"bundle_id": self.bundle_id}

        group = self.select_pane("Rulers")
        controls = self._rulers_controls(group)
        state["ruler_units"] = ax.attr(controls["ruler_units"], ax.VALUE)
        state["grid_color"] = _rgba(ax.attr(controls["grid_color"], ax.VALUE))
        state["gridline_every"] = ax.attr(controls["gridline_every"], ax.VALUE)
        state["gridline_units"] = ax.attr(controls["gridline_units"], ax.VALUE)
        state["subdivisions"] = ax.attr(controls["subdivisions"], ax.VALUE)

        group = self.select_pane("General")
        controls = self._general_controls(group)
        state["transparency_color"] = _rgba(ax.attr(controls["transparency_color"], ax.VALUE))
        state["checkerboard"] = int(ax.attr(controls["checkerboard"], ax.VALUE) or 0)
        return state

    # ---- writing ---------------------------------------------------------

    def write(self, wanted, tries=2):
        """Apply a state dict and confirm it took. Missing keys are left alone.

        Every write goes through the real UI, so any step can lose a race and
        leave the settings half changed. Rather than trust the writes, this
        reads the panes back and retries the whole pass if anything is off —
        and raises naming the settings that would not take, so a failure is
        never mistaken for success. That matters most on the way back: the
        snapshot is only deleted once a restore has been verified.
        """
        from . import state as state_module

        for attempt in range(tries):
            self._write_once(wanted)
            missed = state_module.mismatches(self.read(), wanted)
            if not missed:
                return
        raise PixelmatorError(
            "Pixelmator Pro did not accept: %s." % ", ".join(m.replace("_", " ") for m in missed)
        )

    def _rulers_control(self, key):
        """Re-find one Rulers control from scratch, right before touching it.

        Never hold on to a control across a write. Changing Ruler Units relays
        the pane out, and a control located before that move can be the wrong
        one afterwards — which is how a restore ended up setting Ruler Units
        twice and never touching Gridline Every's units.
        """
        return self._rulers_controls(self.select_pane("Rulers"))[key]

    def _settle_popup(self, key, value, tries=3):
        for _ in range(tries):
            control = self._rulers_control(key)
            if ax.attr(control, ax.VALUE) == value:
                return True
            ax.press_menu_item(control, value)
            time.sleep(SETTLE)
        return ax.attr(self._rulers_control(key), ax.VALUE) == value

    def _settle_field(self, key, value, tries=3):
        for _ in range(tries):
            control = self._rulers_control(key)
            if str(ax.attr(control, ax.VALUE)) == str(value):
                return True
            ax.set_field(control, value)
            time.sleep(SETTLE)
        return str(ax.attr(self._rulers_control(key), ax.VALUE)) == str(value)

    def _write_once(self, state):
        """One pass over the settings, each one confirmed as it is written.

        Order matters: the units pop-ups come first because they change what
        the number fields mean, and every control is looked up again
        immediately before use.
        """
        self.activate()

        if state.get("ruler_units"):
            self._settle_popup("ruler_units", state["ruler_units"])
        if state.get("gridline_units"):
            self._settle_popup("gridline_units", state["gridline_units"])
        if state.get("gridline_every") is not None:
            self._settle_field("gridline_every", state["gridline_every"])
        if state.get("subdivisions") is not None:
            self._settle_field("subdivisions", state["subdivisions"])
        if state.get("grid_color"):
            self._set_color(self._rulers_control("grid_color"), state["grid_color"])

        if state.get("checkerboard") is not None:
            want = int(state["checkerboard"])
            for _ in range(3):
                controls = self._general_controls(self.select_pane("General"))
                if int(ax.attr(controls["checkerboard"], ax.VALUE) or 0) == want:
                    break
                ax.perform(controls["checkerboard"])
                time.sleep(SETTLE)
        if state.get("transparency_color"):
            controls = self._general_controls(self.select_pane("General"))
            self._set_color(controls["transparency_color"], state["transparency_color"])

    # ---- colour wells ----------------------------------------------------

    def _set_color(self, well, rgba, tries=2):
        """Set a colour well by driving the shared Colors panel.

        A colour well has no writable value: the only way in is to open the
        panel it is bound to and change the panel's colour, which the well
        follows live. The panel must be in RGB Sliders mode, where it exposes a
        hex field that takes an exact value.
        """
        target = list(rgba) + [1.0] * (4 - len(rgba))
        for attempt in range(tries):
            self.activate()
            panel = self._open_panel_for(well)
            sliders = self._rgb_mode(panel)
            self._enter_hex(sliders, target)
            time.sleep(SETTLE)
            current = _rgba(ax.attr(well, ax.VALUE))
            if current and all(abs(a - b) < 0.004 for a, b in zip(current[:3], target[:3])):
                return True
            if attempt + 1 < tries:
                # Most likely the well was not bound to the panel — close the
                # panel so the next press opens a freshly bound one.
                panel = self._colors_panel()
                if panel is not None:
                    _close(panel)
                    time.sleep(0.4)
        raise PixelmatorError("Could not set a colour in Pixelmator Pro's Settings.")

    def _open_panel_for(self, well):
        """Press a colour well and return the Colors panel bound to it.

        Pressing a well that already owns the open panel closes it, so any open
        panel is closed first and the well pressed from a known state.
        """
        panel = self._colors_panel()
        if panel is not None:
            _close(panel)
            time.sleep(0.4)
        ax.perform(well)
        for _ in range(20):
            time.sleep(0.15)
            panel = self._colors_panel()
            if panel is not None:
                return panel
        raise PixelmatorError("Pixelmator Pro's Colors panel did not open.")

    @staticmethod
    def _panel_group(panel):
        return next((k for k in ax.children(panel) if ax.attr(k, ax.ROLE) == "AXSplitGroup"), None)

    @staticmethod
    def _has_hex(group):
        return any(
            ax.attr(k, ax.ROLE) == "AXStaticText"
            and (ax.attr(k, ax.VALUE) or "").startswith("Hex Color")
            for k in ax.children(group or [])
        )

    def _rgb_mode(self, panel):
        """Put the Colors panel into RGB Sliders and return its content group.

        The panel remembers whichever mode it was last left in — Colour Wheel,
        HSB Sliders, a palette — and only RGB Sliders offers a hex field. The
        pane is rebuilt asynchronously after the mode changes, so this waits
        for the hex field to actually appear rather than sleeping a fixed
        interval and hoping: a fixed 0.5s wait was enough on the first change
        of a session and not on later ones, which made restores fail partway.
        """
        toolbar = next((k for k in ax.children(panel) if ax.attr(k, ax.ROLE) == "AXToolbar"), None)
        if toolbar is not None:
            for button in ax.children(toolbar):
                if ax.attr(button, ax.DESCRIPTION) == "Color Sliders":
                    ax.perform(button)
                    time.sleep(0.3)
                    break

        group = self._panel_group(panel)
        if group is None:
            raise PixelmatorError("Pixelmator Pro's Colors panel has an unexpected layout.")

        popup = next((k for k in ax.children(group) if ax.attr(k, ax.ROLE) == "AXPopUpButton"), None)
        if popup is not None and ax.attr(popup, ax.VALUE) != "RGB Sliders":
            if self._color_mode is None:
                self._color_mode = ax.attr(popup, ax.VALUE)
            ax.press_menu_item(popup, "RGB Sliders")

        for _ in range(40):
            group = self._panel_group(panel)
            if self._has_hex(group):
                return group
            time.sleep(0.15)
        raise PixelmatorError("Pixelmator Pro's Colors panel would not switch to RGB Sliders.")

    def _restore_color_mode(self, panel):
        group = next((k for k in ax.children(panel) if ax.attr(k, ax.ROLE) == "AXSplitGroup"), None)
        popup = next(
            (k for k in ax.children(group or panel) if ax.attr(k, ax.ROLE) == "AXPopUpButton"), None
        )
        if popup is not None:
            ax.press_menu_item(popup, self._color_mode)
            time.sleep(0.3)

    @staticmethod
    def _enter_hex(group, rgba):
        """Type into the panel's "Hex Color #" and Opacity fields."""
        hex_label = None
        opacity_label = None
        for kid in ax.children(group):
            if ax.attr(kid, ax.ROLE) != "AXStaticText":
                continue
            value = ax.attr(kid, ax.VALUE)
            if value and value.startswith("Hex Color"):
                hex_label = ax.top(kid)
            elif value == "Opacity":
                opacity_label = ax.top(kid)
        if hex_label is None:
            raise PixelmatorError("Pixelmator Pro's Colors panel has no hex field.")
        field = Settings._nearest(group, "AXTextField", hex_label, limit=20.0)
        if field is None:
            raise PixelmatorError("Pixelmator Pro's Colors panel has no hex field.")
        ax.set_field(field, _hex(rgba))
        time.sleep(0.3)
        if opacity_label is not None:
            opacity = Settings._nearest(group, "AXTextField", opacity_label, limit=20.0)
            if opacity is not None:
                ax.set_field(opacity, "%d" % round(rgba[3] * 100))
