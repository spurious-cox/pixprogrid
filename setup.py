"""py2app build for PixProGrid.app — v1.4.0

    ./venv/bin/python setup.py py2app
    cp -R dist/PixProGrid.app /Applications/

Use build.sh instead: it also signs with the Apple Development certificate,
selected by hash and timestamped, which is what keeps the Accessibility grant
alive across rebuilds.
"""

from setuptools import setup

APP = ["main.py"]

# The README ships INSIDE the bundle (Contents/Resources) so it travels with
# the app and nothing depends on ~/My_Applications existing.
DATA_FILES = ["PixProGrid-README.txt"]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "icon/PixProGrid.icns",
    "packages": ["pixprogrid"],
    "plist": {
        "CFBundleName": "PixProGrid",
        "CFBundleDisplayName": "PixProGrid",
        "CFBundleIdentifier": "com.timmccoy.pixprogrid",
        "CFBundleShortVersionString": "1.4.2",
        "CFBundleVersion": "1.4.2",
        "LSMinimumSystemVersion": "13.0",
        "NSHighResolutionCapable": True,
        # A floating utility panel, not an app to switch to: no Dock icon and
        # no menu bar. Dismiss or closing the panel quits it.
        "LSUIElement": True,
        "NSHumanReadableCopyright": "Copyright © 2026 Tim McCoy. All rights reserved.",
        "CFBundleGetInfoString":
            "PixProGrid — hides Pixelmator Pro's grid for screenshots without switching it off.",
    },
}

setup(
    name="PixProGrid",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
