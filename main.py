"""PixProGrid — a floating switch that hides Pixelmator Pro's grid — v1.3.0

Pixelmator Pro will not let some tools work with the grid switched off, so this
does not switch it off. It sets the grid to one gridline every 100% with a
single subdivision, which leaves the only gridlines on the canvas edges, and
paints them light gray. At the same time it turns the checkerboard off and
makes the transparency background light gray, so a screen grab of part of the
canvas comes out clean.

The switch goes back to the user's own settings when it is turned off, when
Dismiss is clicked, and when the app quits. The settings it replaces are written
to disk first, so a crash or a force-quit does not strand them: the next launch
finds the file and puts them back.

The window is a non-activating floating panel. Clicking the switch must not
take the front away from Pixelmator Pro — its Colors panel, which is the only
way to set a colour well, hides the moment Pixelmator stops being active.

v1.1.0  the panel reopens where it was last left, and ⌃⌥⌘G flips the switch
        from any app.
v1.1.1  the button is labelled Dismiss.
v1.2.0  writes are verified and retried, a failed restore keeps the switch
        on and says so, and the panel centres on first launch.
v1.2.1  the panel centres on the true middle of the screen.
v1.3.0  pane switches are waited for rather than timed, every setting is
        confirmed as it is written, and the status line wraps to two lines.
"""

import threading
import traceback

import objc
from AppKit import (
    NSApp,
    NSApplication,
    NSBackingStoreBuffered,
    NSBezelStyleRounded,
    NSButton,
    NSColor,
    NSEvent,
    NSEventMaskKeyDown,
    NSEventModifierFlagCommand,
    NSEventModifierFlagControl,
    NSEventModifierFlagOption,
    NSEventModifierFlagShift,
    NSFloatingWindowLevel,
    NSFont,
    NSLineBreakByWordWrapping,
    NSMakeRect,
    NSPanel,
    NSScreen,
    NSSwitch,
    NSTextField,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskNonactivatingPanel,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskUtilityWindow,
)
from Foundation import NSObject
from PyObjCTools import AppHelper

from pixprogrid import VERSION, ax, state
from pixprogrid.pixelmator import PixelmatorError, Settings

WIDTH = 380.0
MARGIN = 20.0

# Where AppKit stores the panel's last position, so it reopens where it was
# left rather than centred.
FRAME_NAME = "PixProGridPanel"

# Two lines: a failure names the settings that would not take, and on one
# line that message was cut off mid-sentence.
STATUS_HEIGHT = 32.0

# Control-Option-Command-G flips the switch from any app — the point of the
# tool is to reach for it while working in Pixelmator Pro, without hunting for
# the panel. Shift is listed so a stray Shift does not silently match.
HOTKEY_KEY = "g"
HOTKEY_FLAGS = NSEventModifierFlagControl | NSEventModifierFlagOption | NSEventModifierFlagCommand
HOTKEY_MASK = HOTKEY_FLAGS | NSEventModifierFlagShift

BLURB = (
    "Sets Pixelmator Pro's grid to one line every 100% with one subdivision, "
    "in light gray, and turns off the transparency checkerboard — the grid "
    "stays on, so tools that need it keep working, but nothing is drawn over "
    "the canvas.\n\n"
    "Turning the switch off, clicking Dismiss, or quitting puts your own "
    "settings back. ⌃⌥⌘G flips the switch from any app."
)


def label(text, frame, size=11.0, color=None, bold=False):
    field = NSTextField.alloc().initWithFrame_(frame)
    field.setStringValue_(text)
    field.setBezeled_(False)
    field.setDrawsBackground_(False)
    field.setEditable_(False)
    field.setSelectable_(False)
    field.setFont_(NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size))
    if color is not None:
        field.setTextColor_(color)
    field.cell().setWraps_(True)
    field.cell().setLineBreakMode_(NSLineBreakByWordWrapping)
    return field


class Controller(NSObject):
    """Owns the panel and the one piece of state that matters: applied or not."""

    def init(self):
        self = objc.super(Controller, self).init()
        if self is None:
            return None
        self.applied = False
        self.busy = False
        self.panel = None
        self.switch = None
        self.status = None
        self._global_monitor = None
        self._local_monitor = None
        return self

    # ---- window --------------------------------------------------------

    @objc.python_method
    def centre(self, panel):
        """Put the panel in the actual middle of the screen.

        NSWindow's own center() is deliberately high — it lands about a
        quarter of the way down — which does not read as the middle for a
        window this small.
        """
        visible = NSScreen.mainScreen().visibleFrame()
        size = panel.frame().size
        panel.setFrameOrigin_(
            (
                visible.origin.x + (visible.size.width - size.width) / 2.0,
                visible.origin.y + (visible.size.height - size.height) / 2.0,
            )
        )

    @objc.python_method
    def build(self):
        blurb = label("", NSMakeRect(0, 0, WIDTH - 2 * MARGIN, 0))
        blurb.setStringValue_(BLURB)
        blurb.setFrameSize_(
            blurb.cell().cellSizeForBounds_(NSMakeRect(0, 0, WIDTH - 2 * MARGIN, 400))
        )
        blurb_height = blurb.frame().size.height

        # Laid out bottom-up: Dismiss, status line, switch row, then the blurb,
        # whose height depends on how the text wraps at this width.
        dismiss_y = MARGIN
        status_y = dismiss_y + 32 + 12
        switch_y = status_y + STATUS_HEIGHT + 12
        blurb_y = switch_y + 24 + 16
        height = blurb_y + blurb_height + MARGIN

        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, WIDTH, height),
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskUtilityWindow
            | NSWindowStyleMaskNonactivatingPanel,
            NSBackingStoreBuffered,
            False,
        )
        panel.setTitle_("PixPro Grid")
        panel.setLevel_(NSFloatingWindowLevel)
        panel.setHidesOnDeactivate_(False)
        panel.setReleasedWhenClosed_(False)
        panel.setDelegate_(self)
        # setFrameAutosaveName_ reports whether the NAME was accepted, not
        # whether a saved position was found — reading it as the latter left
        # the panel at the origin, in the bottom-left corner. setFrameUsingName_
        # is the one that answers the question, so centre when it finds nothing.
        panel.setFrameAutosaveName_(FRAME_NAME)
        if not panel.setFrameUsingName_(FRAME_NAME):
            self.centre(panel)

        content = panel.contentView()
        blurb.setFrameOrigin_((MARGIN, blurb_y))
        content.addSubview_(blurb)

        switch = NSSwitch.alloc().initWithFrame_(NSMakeRect(MARGIN, switch_y, 40, 24))
        switch.setTarget_(self)
        switch.setAction_(b"toggled:")
        content.addSubview_(switch)
        content.addSubview_(
            label(
                "Screenshot settings",
                NSMakeRect(MARGIN + 52, switch_y + 2, 200, 20),
                size=13.0,
                bold=True,
            )
        )

        status = label(
            "",
            NSMakeRect(MARGIN, status_y, WIDTH - 2 * MARGIN, STATUS_HEIGHT),
            color=NSColor.secondaryLabelColor(),
        )
        content.addSubview_(status)

        dismiss = NSButton.alloc().initWithFrame_(
            NSMakeRect(WIDTH - MARGIN - 90, dismiss_y, 90, 32)
        )
        dismiss.setTitle_("Dismiss")
        dismiss.setBezelStyle_(NSBezelStyleRounded)
        dismiss.setTarget_(self)
        dismiss.setAction_(b"dismiss:")
        content.addSubview_(dismiss)

        self.panel = panel
        self.switch = switch
        self.status = status
        panel.orderFrontRegardless()
        return panel

    # ---- status --------------------------------------------------------

    def setStatus_(self, text):
        self.status.setStringValue_(text)

    @objc.python_method
    def post(self, text):
        """Set the status line from whichever thread is running."""
        self.performSelectorOnMainThread_withObject_waitUntilDone_(b"setStatus:", text, False)

    def finish_(self, args):
        applied, message = args
        self.applied = applied
        self.busy = False
        self.switch.setEnabled_(True)
        self.switch.setState_(1 if applied else 0)
        self.status.setStringValue_(message)

    @objc.python_method
    def done(self, applied, message):
        self.performSelectorOnMainThread_withObject_waitUntilDone_(
            b"finish:", (applied, message), False
        )

    # ---- actions -------------------------------------------------------

    def toggled_(self, sender):
        if self.busy:
            return
        wanted = bool(sender.state())
        self.busy = True
        self.switch.setEnabled_(False)
        self.setStatus_("Applying edited settings…" if wanted else "Restoring your settings…")
        threading.Thread(target=self._work, args=(wanted,), daemon=True).start()

    def dismiss_(self, sender):
        if self.busy:
            return
        if self.applied:
            self.busy = True
            self.switch.setEnabled_(False)
            self.setStatus_("Restoring your settings…")
            threading.Thread(target=self._quit_after_restore, daemon=True).start()
        else:
            NSApp().terminate_(self)

    def windowShouldClose_(self, window):
        self.dismiss_(None)
        return False

    def hotkey_(self, _sender):
        """Flip the switch as if it had been clicked."""
        if self.busy:
            return
        self.switch.setState_(0 if self.switch.state() else 1)
        self.toggled_(self.switch)

    @objc.python_method
    def install_hotkey(self):
        """Watch for ⌃⌥⌘G everywhere, and in our own panel.

        The global monitor only works because the app already holds
        Accessibility access for driving Pixelmator Pro; it observes and never
        swallows the key, so an app that uses the same combination still gets
        it. The monitors are kept on self — dropping the returned tokens stops
        delivery.
        """

        def matches(event):
            typed = event.charactersIgnoringModifiers()
            return (
                typed
                and typed.lower() == HOTKEY_KEY
                and (event.modifierFlags() & HOTKEY_MASK) == HOTKEY_FLAGS
            )

        def globally(event):
            if matches(event):
                self.performSelectorOnMainThread_withObject_waitUntilDone_(
                    b"hotkey:", None, False
                )

        def locally(event):
            if matches(event):
                self.hotkey_(None)
                return None
            return event

        self._global_monitor = NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown, globally
        )
        self._local_monitor = NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
            NSEventMaskKeyDown, locally
        )

    # ---- work ----------------------------------------------------------

    @objc.python_method
    def _work(self, wanted):
        try:
            if wanted:
                with Settings() as settings:
                    original = settings.read()
                    state.save_snapshot(original)
                    settings.write(state.EDITED)
                self.done(True, "Edited settings applied to %s." % _app_name(original))
            else:
                restored = self._restore()
                self.done(False, "Your settings restored%s." % restored)
        except PixelmatorError as error:
            # A failed restore leaves the snapshot on disk, so the switch stays
            # on to show the settings really are still applied, and the status
            # says how to finish the job rather than leaving it looking done.
            self.done(self.applied, self._trouble(wanted, str(error)))
        except Exception:
            traceback.print_exc()
            self.done(self.applied, self._trouble(wanted, "Unexpected error, see Console."))

    @objc.python_method
    def _trouble(self, wanted, message):
        if wanted or not state.load_snapshot():
            return message
        return "%s Your settings are still applied — try again or click Dismiss." % message

    @objc.python_method
    def _restore(self):
        """Put the snapshot back. Returns a suffix for the status line."""
        snapshot = state.load_snapshot()
        if not snapshot:
            return " (nothing to restore)"
        with Settings() as settings:
            settings.write(snapshot)
        state.clear_snapshot()
        return " to %s" % _app_name(snapshot)

    @objc.python_method
    def _quit_after_restore(self):
        """Dismiss only quits once the settings are verifiably back.

        Quitting on a failed restore would close the one window that says so
        and leave Pixelmator Pro changed, so a failure keeps the panel open
        with the switch still on and the reason on the status line.
        """
        try:
            self._restore()
        except PixelmatorError as error:
            self.done(True, self._trouble(False, str(error)))
            return
        except Exception:
            traceback.print_exc()
            self.done(True, self._trouble(False, "Unexpected error, see Console."))
            return
        self.performSelectorOnMainThread_withObject_waitUntilDone_(b"quit:", None, True)

    def quit_(self, _sender):
        self.applied = False
        NSApp().terminate_(self)

    # ---- launch --------------------------------------------------------

    @objc.python_method
    def recover(self):
        """Undo a session that ended without restoring (crash, force-quit)."""
        if not state.load_snapshot():
            self.setStatus_("Ready.")
            return
        self.busy = True
        self.switch.setEnabled_(False)
        self.setStatus_("Putting settings back from an interrupted session…")

        def work():
            try:
                self._restore()
                self.done(False, "Settings from an interrupted session were put back.")
            except PixelmatorError as error:
                self.done(False, str(error))

        threading.Thread(target=work, daemon=True).start()


def _app_name(snapshot):
    return (
        "Pixelmator Pro Creator Studio"
        if snapshot.get("bundle_id") == "com.apple.pixelmator"
        else "Pixelmator Pro"
    )


class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, notification):
        self.controller = Controller.alloc().init()
        self.controller.build()
        if not ax.is_trusted(prompt=True):
            self.controller.setStatus_(
                "Waiting for Accessibility access — grant it in System Settings, then relaunch."
            )
            return
        self.controller.install_hotkey()
        self.controller.recover()

    def applicationWillTerminate_(self, notification):
        # Last line of defence: Dismiss and the switch already restore, but a
        # Quit from anywhere else must not leave the edited settings behind.
        if state.load_snapshot() is None:
            return
        try:
            with Settings() as settings:
                settings.write(state.load_snapshot())
            state.clear_snapshot()
        except Exception:
            traceback.print_exc()

    def applicationShouldTerminateAfterLastWindowClosed_(self, sender):
        return True


def main():
    app = NSApplication.sharedApplication()
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    print("PixProGrid %s" % VERSION)
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
