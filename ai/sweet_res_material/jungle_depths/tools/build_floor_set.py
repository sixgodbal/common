"""Cut the 3x3 floor sheet into nine 40x40 seamless floor tiles."""

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
ELEM = OUT / "elements"
ELEM.mkdir(parents=True, exist_ok=True)

BG = np.array([247, 241, 227], dtype=np.int16)

NAMES = [
    ["grass_plain", "grass_flowers", "grass_moss"],
    ["stone_plain", "stone_moss", "stone_leaves"],
    ["earth_plain", "earth_leaves", "water_plain"],
]
CELL = 320


def main():
    sheet = Image.open(OUT / "jungle_depths_floors_b.png").convert("RGB")
    assert sheet.size == (960, 960), sheet.size
    for r, row in enumerate(NAMES):
        for c, name in enumerate(row):
            cell = sheet.crop((c * CELL, r * CELL, (c + 1) * CELL, (r + 1) * CELL))
            a = np.array(cell).astype(np.int16)
            mask = np.abs(a - BG).max(axis=2) > 20
            ys, xs = np.where(mask)
            x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
            side = int(min(x1 - x0, y1 - y0) * 0.95)
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            cell = cell.crop((cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2))
            tile = cell.resize((40, 40), Image.LANCZOS)
            if name == "water_plain":
                # mirror-tile to guarantee seamless edges, then squeeze back to 40
                m = Image.new("RGB", (80, 80))
                m.paste(tile, (0, 0))
                m.paste(tile.transpose(Image.FLIP_LEFT_RIGHT), (40, 0))
                m.paste(tile.transpose(Image.FLIP_TOP_BOTTOM), (0, 40))
                m.paste(tile.transpose(Image.ROTATE_180), (40, 40))
                tile = m.resize((40, 40), Image.LANCZOS)
            tile.save(ELEM / f"floor2_{name}.png")
            print("floor2", name)

    # tiling previews 6x6 at 4x
    for row in NAMES:
        for name in row:
            tile = Image.open(ELEM / f"floor2_{name}.png").convert("RGB")
            big = Image.new("RGB", (240, 240))
            for r in range(6):
                for c in range(6):
                    big.paste(tile, (c * 40, r * 40))
            big.resize((960, 960), Image.NEAREST).save(OUT / f"_tiling2_{name}.png")
    print("tiling previews OK")


if __name__ == "__main__":
    main()
