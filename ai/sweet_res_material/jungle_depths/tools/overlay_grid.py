"""Overlay a 40x40 grid on a 1600x1600 map preview to check cell alignment."""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

src = Path(sys.argv[1]) if len(sys.argv) > 1 else (
    Path(__file__).resolve().parents[1] / "out" / "jungle_depths_map_40x40_1600.png"
)
dst = src.with_name(src.stem + "_gridcheck.png")

im = Image.open(src).convert("RGBA")
w, h = im.size
if (w, h) != (1600, 1600):
    raise SystemExit(f"expected 1600x1600, got {w}x{h}")

overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
d = ImageDraw.Draw(overlay)
for i in range(0, 1601, 40):
    d.line([(i, 0), (i, 1600)], fill=(255, 40, 40, 150), width=1)
    d.line([(0, i), (1600, i)], fill=(255, 40, 40, 150), width=1)

# highlight the 4x2 centre gate block (cols 18-21, rows 19-20)
d.rectangle([18 * 40, 19 * 40, 22 * 40 - 1, 21 * 40 - 1], outline=(0, 220, 255, 255), width=2)

Image.alpha_composite(im, overlay).convert("RGB").save(dst)
print("OK ->", dst)
