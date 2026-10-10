#!/bin/zsh
# Build, sign and install PixProGrid.app — v1.5.6
#
# Signing uses the Developer ID certificate (expires 2027-02-01), the identity
# notarization accepts. A STABLE signing identity matters here because macOS ties the
# Accessibility grant to the code signature: an ad-hoc signature gets a fresh
# checksum on every build, which would drop PixProGrid out of System Settings >
# Privacy & Security > Accessibility after each rebuild, and without that grant
# the app cannot touch Pixelmator Pro's Settings at all.
#
# Two things to know about this identity:
#
#   * It is selected by SHA-1 HASH, not by name. The expired 2023 certificate is
#     still in the keychain under exactly the same name, and signing by name can
#     pick the dead one.
#   * --timestamp is not optional. A timestamped signature stays valid after the
#     certificate expires; without it, every app signed here breaks on that date.
#
# When the certificate is renewed again, put the new hash here:
#   security find-identity -p codesigning | grep "Developer ID Application"
#
# v1.4.0 signs every nested Mach-O before sealing the bundle. Signing only the
# bundle leaves py2app's 128 inner binaries with whatever signature they
# arrived with, and Apple rejects the whole submission for them:
#   "The binary is not signed with a valid Developer ID certificate."
#   "The signature does not include a secure timestamp."
#   "The executable does not have the hardened runtime enabled."
# Match on WHAT A FILE IS, not what it is called: Contents/MacOS/python and the
# Python framework binary are Mach-O with no extension, so globbing *.dylib and
# *.so misses exactly the files Apple names first.
set -e
cd "${0:A:h}"

SIGN_ID="4208ABA3EC12F24C1F09C7BB624EFF68B44259DB"   # Developer ID Application (was Apple Development)

if ! security find-identity -p codesigning | grep -q "$SIGN_ID"; then
    echo "error: signing identity $SIGN_ID not in keychain (renewed cert?)" >&2
    exit 1
fi

echo "==> restoring Pixelmator Pro if a session was left applied"
# A running copy would otherwise be killed mid-session, leaving the edited
# settings in place. The snapshot is on disk, so this works regardless.
./venv/bin/python selftest.py restore 2>/dev/null || true

echo "==> killing any running instance"
pkill -x PixProGrid 2>/dev/null || true
sleep 1

echo "==> building"
rm -rf build dist
./venv/bin/python setup.py py2app >/dev/null

# macOS 26+ draws an app that has only an .icns shrunk onto a plain plate.
# The Icon Composer document compiles into Assets.car, which macOS 26+ uses
# instead; the .icns from setup.py is still what macOS 13-25 show.
~/bin/glass_icon dist/PixProGrid.app icon/AppIcon.icon

echo "==> signing nested binaries with Developer ID ($SIGN_ID)"
find dist/PixProGrid.app -type f -print0 | while IFS= read -r -d $'\0' f; do
    if file -b "$f" 2>/dev/null | grep -q 'Mach-O'; then
        codesign --force --timestamp --options runtime --sign "$SIGN_ID" "$f" 2>/dev/null || true
    fi
done
# Nested bundles are sealed as units, after their own contents.
find dist/PixProGrid.app -name '*.framework' -print0 2>/dev/null \
    | xargs -0 -n1 -I{} codesign --force --timestamp --options runtime --sign "$SIGN_ID" {} 2>/dev/null || true

echo "==> signing the bundle with Developer ID ($SIGN_ID)"
codesign --force --timestamp --options runtime \
    --entitlements "$HOME/My_Applications/_signing/pixpro.entitlements" --sign "$SIGN_ID" dist/PixProGrid.app
codesign --verify --strict dist/PixProGrid.app

# Installing is the default here and in every other project's build.sh.
# --no-install builds without touching /Applications.
if [[ "$1" == "--no-install" ]]; then
    echo "==> --no-install: leaving /Applications alone"
    exit 0
fi

echo "==> installing to /Applications"
rm -rf /Applications/PixProGrid.app
cp -R dist/PixProGrid.app /Applications/
xattr -dr com.apple.quarantine /Applications/PixProGrid.app 2>/dev/null || true

echo "==> installed:"
codesign -dv /Applications/PixProGrid.app 2>&1 | grep -E "Identifier=|Authority="
plutil -extract CFBundleShortVersionString raw /Applications/PixProGrid.app/Contents/Info.plist
echo "==> running instances: $(pgrep -x PixProGrid | wc -l | tr -d ' ')"
echo
echo "Signed, not notarized. To publish, follow with:"
echo "  ~/My_Applications/_signing/pixpro_release.sh notarize /Applications/PixProGrid.app"
echo
echo "The signing identity is stable, so the Accessibility grant should survive."
echo "If the panel says it is waiting for access, remove PixProGrid from"
echo "System Settings > Privacy & Security > Accessibility and add it again."
