=============================================================================
 PixProGrid — Temporary Screenshot Settings for Pixelmator Pro
=============================================================================

PixProGrid is a small macOS utility that makes Pixelmator Pro's grid
invisible without switching it off, so part of the canvas can be screen-
grabbed cleanly while the tools that require a grid keep working. It is a
floating panel with one switch: on applies the screenshot settings, off puts
your own settings back.

WHAT IT IS MOSTLY FOR. The common use is simply taking a screenshot of the
artwork itself — grabbing what is on the canvas with no gridline segments
cutting across it, and no checkerboard behind the transparent areas.

Turning the grid off instead is not an option: the tools that depend on the
grid stop working without it, and the screen grab itself does not happen with
the grid switched off. Making the gridlines invisible while the grid stays on
is the way around both. Switch on, grab, switch off.

The grid is not disabled. It is set to one gridline every 100% with a single
subdivision, which places the only gridlines on the canvas edges, and its
colour is set to light gray. At the same time the transparency checkerboard
is switched off and the transparency colour set to light gray, so
transparent areas grab as flat light gray instead of a checker pattern.

App:      /Applications/PixProGrid.app
Source:   this repository
Snapshot: ~/Library/Application Support/PixProGrid/snapshot.json
Shortcut: Control-Option-Command-G  (from any app, while PixProGrid runs)


-----------------------------------------------------------------------------
 HOW TO USE IT
-----------------------------------------------------------------------------

    1. Launch /Applications/PixProGrid.app. There is no Dock icon and no
       menu bar — the panel is the app. The first run needs Accessibility
       access (see below).

    2. Flip the switch ON. Your own settings are snapshotted first, then
       the screenshot settings are applied. It takes a few seconds while
       the Settings window is driven, and the status line reports what
       happened.

    3. Take the screen grab.

    4. Flip the switch OFF to put your own settings back, or click Dismiss
       to restore and quit. Control-Option-Command-G flips the switch from
       whatever app you are in, as long as PixProGrid is running.

USING IT, below, covers each control in detail.


-----------------------------------------------------------------------------
 FIRST RUN — ACCESSIBILITY ACCESS IS REQUIRED
-----------------------------------------------------------------------------

PixProGrid changes Pixelmator Pro's settings by driving its Settings window
through the macOS Accessibility API. Without that permission it can do
nothing at all, and the panel's status line says so.

    1. Launch /Applications/PixProGrid.app
    2. System Settings > Privacy & Security > Accessibility
    3. Add (or switch on) PixProGrid
    4. Relaunch PixProGrid

The permission is tied to the app's code signature, so build.sh signs with a
stable identity precisely to make this grant survive rebuilds; an ad-hoc
signature would get a new checksum each build and drop the app out of the
Accessibility list every time.

That identity is a Developer ID certificate, and the signature is
timestamped so it stays valid after the certificate expires.

The app has no Dock icon and no menu bar (LSUIElement). The panel IS the
app: closing it or clicking Dismiss quits.


-----------------------------------------------------------------------------
 WHAT THE SWITCH CHANGES
-----------------------------------------------------------------------------

Settings > General
    Transparency colour        light gray, #D3D3D3
    Checkerboard               off

Settings > Rulers
    Ruler Units                Percent
    Grid colour                light gray, #D3D3D3
    Gridline Every             100 Percent
    Subdivisions               1

(In Pixelmator Pro 3.8 the General row is labelled "Background:" rather
than "Transparency:". PixProGrid accepts either.)

Everything else in Pixelmator Pro is left alone. Guides, smart guides,
ruler visibility and the grid's on/off state are not touched.


-----------------------------------------------------------------------------
 USING IT
-----------------------------------------------------------------------------

SWITCH ON     Reads your current settings, writes them to the snapshot file,
              then applies the settings above. Takes a few seconds: the
              Settings window opens, the panes are driven, and the window
              closes again. Pixelmator Pro comes to the front while this
              happens and stays there — the panel is a non-activating
              window and never steals the front from it.

SWITCH OFF    Puts the snapshotted settings back, confirms every setting
              actually took, and only then deletes the snapshot. If
              something did not take it says so, leaves the switch ON —
              because the settings really are still applied — and keeps
              the snapshot so you can try again or click Dismiss.

DISMISS       Same as switching off, then quits — but only if the restore
              succeeded. On failure it stays open with the reason showing,
              rather than closing the one window that could tell you.

CLOSE BOX     Same as Dismiss.

QUIT          Restores before terminating, from any quit path.

⌃⌥⌘G          Flips the switch from whatever app you are in. It does NOT
              launch PixProGrid — the shortcut is a monitor installed by
              the running app, so it works only once PixProGrid is up.
              Launch it from /Applications first; the shortcut then works
              for the rest of that session. The key is observed, not
              swallowed, so an app that uses the same combination still
              receives it.

The status line under the switch reports what happened, including which
Pixelmator build was changed.

The panel opens in the middle of the screen the first time, and after
that wherever you last left it.


-----------------------------------------------------------------------------
 THE SAFETY NET
-----------------------------------------------------------------------------

Your settings are written to the snapshot file BEFORE anything is changed.
That ordering is the whole point: if PixProGrid is force-quit, crashes, or
the Mac restarts while the screenshot settings are applied, the settings are
not stranded with nothing on screen to explain them.

The next launch finds the snapshot, puts the settings back, and reports
"Settings from an interrupted session were put back." The snapshot is
deleted only once the restore has succeeded.

build.sh also runs a restore before it kills a running copy, so rebuilding
mid-session cannot strand the settings either.


-----------------------------------------------------------------------------
 WHY IT WORKS THIS WAY (and why the obvious approach does not)
-----------------------------------------------------------------------------

The obvious approach — write the values into Pixelmator Pro's preferences
file — does not work, and this was verified directly rather than assumed.

Both builds are sandboxed. Their preferences live inside the app container,
and cfprefsd hands the running app a cached copy. An external write to that
plist is ignored by the running app entirely, and is liable to be overwritten
when the app next flushes its own preferences. Writing gridSubdivision from
outside changed the file and changed nothing in Pixelmator Pro.

Driving the Settings window through the Accessibility API is what works.
AppleScript's System Events was tried first and rejected: it cannot commit a
text field (the typed value reverts the moment the field redraws) and it
cannot set a colour well at all. PyObjC talking to the Accessibility API
directly does both.

The specific techniques, all of which took some finding:

TEXT FIELDS      AXFocused = True, then AXValue, then the AXConfirm action.
                 Setting AXValue alone only changes what is drawn on screen;
                 Pixelmator Pro's model keeps the old number. AXConfirm is
                 what ends editing and applies the value.

POP-UP BUTTONS   Ignore AXValue writes. The button must be pressed to open
                 its menu, then the wanted menu item pressed.

COLOUR WELLS     Have no writable value. The only way in is to press the
                 well, which opens the shared Colors panel bound to it, and
                 change the panel's colour — the well follows live. The
                 panel must first be put into RGB Sliders mode, where it
                 exposes a "Hex Color #" field that takes an exact value.
                 In its default Color Wheel mode the only text field is
                 Opacity, and typing a hex value there sets the alpha to 0.

FRONTMOST        Pixelmator Pro must be the active app for the colour work:
                 the Colors panel hides the instant Pixelmator deactivates.
                 This is why PixProGrid's panel is non-activating.

PANEL BINDING    Pressing a colour well that already owns the open Colors
                 panel closes it. PixProGrid closes any open panel first,
                 then presses the well, so the panel is always freshly bound.

FINDING CONTROLS The Settings window's accessibility title is the name of
                 the selected pane ("General", "Rulers", ...), which is how
                 it is located and how pane switches are confirmed. Control
                 order within a pane is NOT stable — Gridline Every and
                 Subdivisions come back in either order and swap places
                 after an edit — so every control is matched to its label by
                 vertical position, never by index.


-----------------------------------------------------------------------------
 BOTH PIXELMATOR BUILDS
-----------------------------------------------------------------------------

Two separate apps with separate preferences are installed on this Mac, and
PixProGrid supports both:

    com.apple.pixelmator             Pixelmator Pro Creator Studio 4.3
    com.pixelmatorteam.pixelmator.x  Pixelmator Pro 3.8

If both are running, the active one is used, so the app follows whichever
Pixelmator you are actually working in. The snapshot records which build it
came from, and the status line names it.


-----------------------------------------------------------------------------
 KNOWN BEHAVIOUR AND LIMITS
-----------------------------------------------------------------------------

COLOUR ROUND TRIP
    Colours are restored through the Colors panel's sRGB hex field, which is
    8-bit. A colour that did not originate as 8-bit sRGB shifts by at most
    1/255 per channel on its first round trip and is stable from then on.
    Pixelmator Pro 3.8's default grid colour is such a colour; Creator
    Studio 4.3's is already exactly 8-bit and round-trips unchanged.

EVERY WRITE IS VERIFIED
    These settings are changed by driving a real user interface, so any
    step can lose a race. Rather than trust the writes, PixProGrid reads
    the panes back afterwards, retries the whole pass once if anything is
    off, and reports by name any setting that would not take. The snapshot
    is deleted only after a restore has been verified.

VISIBLE WINDOW ACTIVITY
    Applying and restoring open and close the Settings window and briefly
    the Colors panel. This is unavoidable — they are the mechanism, not a
    side effect — and takes a few seconds each way. The switch is disabled
    while it is working.

PIXELMATOR PRO MUST BE RUNNING
    If it is not, the status line says so and nothing is changed.

DOCUMENT SETTINGS
    These are application preferences, so they apply to every open document,
    not just the front one.


-----------------------------------------------------------------------------
 FILES
-----------------------------------------------------------------------------

main.py                    The panel, the switch, the hotkey, and the
                           launch-time crash recovery.
pixprogrid/ax.py           Thin wrapper over the Accessibility API.
pixprogrid/pixelmator.py   Reads and writes Pixelmator Pro's settings;
                           finds controls, drives the Colors panel.
pixprogrid/state.py        The edited settings, and snapshot save/load.
selftest.py                Headless driver test (see below).
uitest.py                  End-to-end test that presses the app's own
                           switch and checks Pixelmator Pro afterwards.
setup.py                   py2app configuration.
build.sh                   Build, sign, install.
icon/                      The app icon (see icon/README.txt).


-----------------------------------------------------------------------------
 REBUILDING
-----------------------------------------------------------------------------

    ./build.sh

build.sh restores any applied session, kills a running copy, builds with
py2app, signs with Developer ID, and installs to
/Applications.

The icon is described in icon/README.txt.


-----------------------------------------------------------------------------
 TESTING
-----------------------------------------------------------------------------

Test the driver without a window in the way:

    ./venv/bin/python selftest.py read        show current settings
    ./venv/bin/python selftest.py apply       snapshot, then apply
    ./venv/bin/python selftest.py restore     put the snapshot back
    ./venv/bin/python selftest.py roundtrip   apply, verify, restore, verify

"roundtrip" is the useful one: it reports mismatches in both directions and
should print "none" twice.

Test the panel wiring, with a copy of the app already running:

    ./venv/bin/python uitest.py <pid>

This presses the app's own switch through the Accessibility API, reads
Pixelmator Pro back to confirm the settings landed, presses it again, and
confirms your settings returned with no snapshot left behind.


-----------------------------------------------------------------------------
 VERSION HISTORY
-----------------------------------------------------------------------------

v1.0.0  (2026-08-03)
    Floating non-activating panel with a switch and a Cancel button.
    Applies and
    restores the six settings above across both Pixelmator Pro builds.
    Snapshot written before any change, with restore on switch-off,
    Cancel, close, quit, and on the next launch after an interrupted
    session. Verified apply/restore round trips on Creator Studio 4.3
    and Pixelmator Pro 3.8, plus a SIGKILL-and-relaunch recovery test.

v1.1.0  (2026-08-03)
    The panel reopens where it was last left rather than centred, and
    Control-Option-Command-G flips the switch from any app. Application
    icon built from gridImage.jpg.

v1.1.1  (2026-08-03)
    The Cancel button is relabelled Dismiss.

v1.2.0  (2026-08-03)
    Restore reliability. The Colors panel remembers whichever mode it was
    last left in, and only RGB Sliders has a hex field; the mode switch
    was given a fixed 0.5s to rebuild the pane, which was enough on the
    first colour of a session and not on later ones. Restores therefore
    failed partway through the colour step, left the snapshot in place,
    and flipped the switch back on — Dismiss then retried and completed
    the job, which is exactly how it looked from the outside. The switch
    now waits for the hex field to appear instead of sleeping, every
    write is read back and retried, and a failed restore says which
    settings would not take. Also fixes the panel opening in the
    bottom-left corner: setFrameAutosaveName_ reports whether the NAME
    was accepted, not whether a saved position existed, so the centring
    call never ran.

v1.2.1  (2026-08-03)
    The panel centres on the true middle of the usable screen. AppKit's
    own center() sits a window about a quarter of the way down.

v1.3.0  (2026-08-03)
    The last of the fixed-timer races. Three places pressed a control and
    waited a set interval instead of waiting for the result: the Settings
    pane switch could hand back the previous pane's contents, and opening
    a pop-up menu could read it before it was populated and then leave it
    hanging open, breaking the next step. With Ruler Units set to Inches
    this showed up as "did not accept: gridline units" — everything else
    restored and the gridline units alone stayed on Percent. All three now
    wait for the state they need, every setting is confirmed as it is
    written rather than only at the end of the pass, and the status line
    wraps to two lines so a failure message is no longer cut off.


-----------------------------------------------------------------------------
v1.3.1  (2026-08-05)
    Re-signed with the renewed Apple Development certificate instead of the
    self-signed one, selected by hash and timestamped. No code changes.


v1.3.2  (2026-08-10)
    The README ships inside the bundle (Contents/Resources) rather than being
    read from outside the app, so the app carries its own documentation and
    depends on no external path. Packaging only; no code changed.


v1.3.3  (2026-09-13)
    Documentation release; no change to the effect. Adds a HOW TO USE IT
    section — numbered steps from selecting the layer, through every dialog
    field and its units, to what the result group contains — and fills in a
    version history that had stopped one release short of the shipping build.
    The copy inside the bundle was refreshed with it, so the Read Me button
    shows the same text.

    Also: the README now says what the app is mostly for — screenshots of the
    artwork itself, with no gridline segments across it and no checkerboard
    behind the transparent areas — and why the grid cannot simply be switched
    off instead. build.sh (v1.4.0) now signs every nested Mach-O before
    sealing the bundle; signing only the bundle left py2app's inner binaries
    as they arrived and Apple rejected the submission for them. The package's
    own VERSION constant, still 1.3.1 while setup.py said 1.3.2, was
    corrected.


v1.4.0  (2026-09-13)  — current
    Checks for a newer release, from an Updates… button beside Dismiss. It asks GitHub for
    the newest published tag and reports what it finds, offering the releases
    page and the `brew upgrade` line — it never downloads or replaces itself,
    because a running bundle cannot safely overwrite its own files. Versions are
    compared as integers, so 3.10.0 counts as newer than 3.9.0 rather than
    older.


-----------------------------------------------------------------------------
 Copyright (c) 2026 Timothy McCoy. All rights reserved.

 Developed with the support of Claude (Anthropic) — design, code, and
 testing assistance for versions 1.0.0 through 1.3.1.
=============================================================================
