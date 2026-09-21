# PixProGrid 1.4.1

Makes Pixelmator Pro's grid invisible without switching it off, so the canvas
can be screen-grabbed cleanly while the tools that need a grid keep working.

### [⬇︎ Download the latest release](https://github.com/spurious-cox/pixprogrid/releases/latest)

Notarized and stapled by Apple — open the DMG and drag PixProGrid to Applications,
or install it with Homebrew:

```
brew install --cask spurious-cox/tap/pixprogrid
```
Requires Pixelmator Pro. Both the 3.x build and the Creator Studio build work;
the app binds to whichever one is in front or has a document open.

## Why it exists

The common use is simply taking a screenshot of the artwork itself — no
gridline segments cutting across it, and no checkerboard behind the transparent
areas. Turning the grid off instead is not an option: the tools that depend on
the grid stop working without it, and the screen grab itself does not happen
with the grid switched off. Making the gridlines invisible while the grid stays
on is the way around both.

## Using it

1. Launch PixProGrid. There is no Dock icon and no menu bar — the panel is the
   app. The first run needs Accessibility access (below).
2. Flip the switch **on**. Your own settings are snapshotted first, then the
   screenshot settings are applied; the status line reports what happened.
3. Take the screen grab.
4. Flip the switch **off** to put your settings back, or click **Dismiss** to
   restore and quit. **⌃⌥⌘G** flips the switch from any app while PixProGrid
   is running.

## What the switch changes

The grid is set to one gridline every 100% with a single subdivision, which
leaves gridlines only on the canvas edges, and its color to light gray. The
transparency checkerboard is switched off and the transparency color set to
light gray, so transparent areas grab as flat gray.

## Accessibility access is required

PixProGrid drives Pixelmator Pro's Settings window through the macOS
Accessibility API, so it needs **System Settings → Privacy & Security →
Accessibility**. Without it the panel's status line says so and nothing else
works.

## The safety net

Your settings are written to a snapshot file *before* anything is changed. If
PixProGrid is force-quit or the Mac restarts while the screenshot settings are
applied, the next launch finds the snapshot, puts the settings back, and says
so. The snapshot is deleted only once the restore has succeeded.

## Building

```
./build.sh
```

Signing uses a Developer ID certificate selected by SHA-1 hash and timestamped,
which is what keeps macOS's Automation grant alive across rebuilds.
`~/My_Applications/_signing/pixpro_release.sh all <App>` signs and notarizes;
`pixpro_publish.sh <App>` wraps it in the DMG and updates the cask.

## License

MIT. See [LICENSE](LICENSE).
