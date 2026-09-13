"""Build PixProGrid.icns from a source image — v1.1.0

    /usr/bin/python3 build_icon.py ../PixProGridIcon.png

The source does not have to be square: it is scaled to fit and centred on a
transparent square canvas, so nothing is cropped or stretched. Writes
PixProGrid.iconset/ and runs iconutil over it.

v1.1.0 — MARGIN dropped to 0. The source artwork already carries its own
margin, so the 6% inset applied here shrank the icon a second time. The source
is now drawn edge to edge and is the only thing deciding how much breathing
room the icon has. (Same fix as PixProTransform's build_icon.py v1.1.0.)
"""

import os
import subprocess
import sys

from AppKit import (
    NSBitmapImageFileTypePNG,
    NSBitmapImageRep,
    NSCalibratedRGBColorSpace,
    NSCompositingOperationSourceOver,
    NSGraphicsContext,
    NSImage,
    NSMakeRect,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ICONSET = os.path.join(HERE, "PixProGrid.iconset")

# Zero: the margin belongs in the artwork, not here. Insetting a source that
# was already drawn with its own margin shrinks the icon twice over.
MARGIN = 0.0

# name, pixel size — the set iconutil expects.
SIZES = [
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
]


def render(source, size):
    """The source scaled to fit a transparent square of `size` pixels."""
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, size, size, 8, 4, True, False, NSCalibratedRGBColorSpace, 0, 0
    )
    context = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.setCurrentContext_(context)

    box = size * (1.0 - 2 * MARGIN)
    width, height = source.size()
    scale = min(box / width, box / height)
    draw_width, draw_height = width * scale, height * scale
    source.drawInRect_fromRect_operation_fraction_(
        NSMakeRect((size - draw_width) / 2, (size - draw_height) / 2, draw_width, draw_height),
        NSMakeRect(0, 0, width, height),
        NSCompositingOperationSourceOver,
        1.0,
    )

    NSGraphicsContext.restoreGraphicsState()
    return rep.representationUsingType_properties_(NSBitmapImageFileTypePNG, {})


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = os.path.expanduser(sys.argv[1])
    source = NSImage.alloc().initWithContentsOfFile_(path)
    if source is None:
        sys.exit("Could not read %s" % path)
    print("source: %s  %gx%g" % (path, source.size().width, source.size().height))

    os.makedirs(ICONSET, exist_ok=True)
    for name, size in SIZES:
        data = render(source, size)
        data.writeToFile_atomically_(os.path.join(ICONSET, name), True)
    print("wrote %d images to %s" % (len(SIZES), ICONSET))

    icns = os.path.join(HERE, "PixProGrid.icns")
    subprocess.run(["iconutil", "-c", "icns", ICONSET, "-o", icns], check=True)
    print("built %s (%d bytes)" % (icns, os.path.getsize(icns)))


if __name__ == "__main__":
    main()
