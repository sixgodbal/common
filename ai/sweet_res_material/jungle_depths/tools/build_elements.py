"""Cut the 4x4 element sheet into game-size 40px assets.

Sheet: 1280x1920, 4 cols x 4 rows, each cell 320x480.
Row 1 = floors (40x40), rows 2-4 = props (40x60 canvas, base bottom-center).
Also cuts the 4x2 gate into 160x100.
"""

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
ELEM = OUT / "elements"
ELEM.mkdir(parents=True, exist_ok=True)

BG = np.array([247, 241, 227], dtype=np.int16)
CELL_W, CELL_H = 320, 480
COLS, ROWS = 4, 4

FLOOR_NAMES = ["floor_stone", "floor_moss", "floor_earth", "floor_water"]
PROP_NAMES = [
    ["wall_tree", "wall_bush", "wall_root", "wall_stump"],
    ["brick_log", "brick_sapling", "brick_bush", "brick_stump"],
    ["brick_snake", "wall_snake_totem", "wall_fern", None],
]

PROP_W, PROP_H = 40, 60
OUTLINE = (47, 74, 40, 255)


def remove_bg(cell: Image.Image) -> Image.Image:
    """Remove cream background components that touch the cell border."""
    a = np.array(cell.convert("RGB")).astype(np.int16)
    near = (np.abs(a - BG).max(axis=2) <= 24)
    lbl, n = ndimage.label(near)
    if n == 0:
        return cell.convert("RGBA")
    border = set(lbl[0, :].tolist()) | set(lbl[-1, :].tolist())
    border |= set(lbl[:, 0].tolist()) | set(lbl[:, -1].tolist())
    border.discard(0)
    alpha = np.full(near.shape, 255, dtype=np.uint8)
    for i in border:
        alpha[lbl == i] = 0
    # drop cell-edge artifacts (panel dividers / shading seams)
    alpha[:3, :] = 0
    alpha[-3:, :] = 0
    alpha[:, :3] = 0
    alpha[:, -3:] = 0
    rgba = np.dstack([np.array(cell.convert("RGB")), alpha])
    return Image.fromarray(rgba, "RGBA")


def bleed_colors(im: Image.Image, steps: int = 4) -> Image.Image:
    """Push opaque colors into transparent pixels to avoid dark/cream fringes."""
    a = np.array(im).astype(np.float32)
    rgb, alpha = a[:, :, :3], a[:, :, 3]
    known = alpha > 0
    for _ in range(steps):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(alpha.shape, dtype=np.float32)
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            shifted_rgb = np.roll(np.roll(rgb, dy, axis=0), dx, axis=1)
            shifted_ok = np.roll(np.roll(known, dy, axis=0), dx, axis=1)
            acc += shifted_rgb * shifted_ok[:, :, None]
            cnt += shifted_ok
        fill = (~known) & (cnt > 0)
        rgb[fill] = acc[fill] / cnt[fill][:, None]
        known = known | fill
    return Image.fromarray(np.dstack([rgb, alpha]).astype(np.uint8), "RGBA")


def add_outline(im: Image.Image, color=OUTLINE) -> Image.Image:
    a = np.array(im)
    alpha = a[:, :, 3] > 0
    if not alpha.any():
        return im
    edge = alpha & ~ndimage.binary_erosion(alpha, iterations=1)
    a[edge] = color
    return Image.fromarray(a, "RGBA")


def keep_largest(im: Image.Image) -> Image.Image:
    """Keep only the biggest opaque blob, dropping panel-divider bands and specks."""
    a = np.array(im)
    mask = a[:, :, 3] > 0
    if not mask.any():
        return im
    lbl, n = ndimage.label(mask)
    if n <= 1:
        return im
    sizes = ndimage.sum(mask, lbl, range(1, n + 1))
    keep = int(np.argmax(sizes)) + 1
    a[:, :, 3] = np.where(lbl == keep, 255, 0)
    return Image.fromarray(a, "RGBA")


def fit_prop(im: Image.Image) -> Image.Image:
    """Scale prop to fit 40x56, bottom-center on a 40x60 canvas, 1px outline."""
    im = keep_largest(im)
    bbox = im.getbbox()
    if not bbox:
        return Image.new("RGBA", (PROP_W, PROP_H), (0, 0, 0, 0))
    im = im.crop(bbox)
    w, h = im.size
    scale = min((PROP_W - 2) / w, (PROP_H - 6) / h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    # binarize alpha so the result stays pixel-crisp
    a = np.array(im)
    a[:, :, 3] = np.where(a[:, :, 3] >= 96, 255, 0)
    im = Image.fromarray(a, "RGBA")
    im = add_outline(im)
    canvas = Image.new("RGBA", (PROP_W, PROP_H), (0, 0, 0, 0))
    x = (PROP_W - nw) // 2
    y = PROP_H - nh
    canvas.alpha_composite(im, (x, y))
    return canvas


def cut_floor(cell: Image.Image) -> Image.Image:
    cell = cell.crop((0, 20, CELL_W, CELL_H))
    a = np.array(cell.convert("RGB")).astype(np.int16)
    mask = np.abs(a - BG).max(axis=2) > 24
    ys, xs = np.where(mask)
    if len(xs) == 0:
        raise SystemExit("empty floor cell")
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    side = min(x1 - x0, y1 - y0)
    # crop the central 88% square to skip rounded corners / borders
    side = int(side * 0.88)
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    box = (cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2)
    tile = cell.crop(box).resize((40, 40), Image.LANCZOS)
    return tile.convert("RGB")


def main() -> None:
    sheet = Image.open(OUT / "jungle_depths_elements_a.png").convert("RGB")
    assert sheet.size == (COLS * CELL_W, ROWS * CELL_H), sheet.size

    for c, name in enumerate(FLOOR_NAMES):
        cell = sheet.crop((c * CELL_W, 0, (c + 1) * CELL_W, CELL_H))
        cut_floor(cell).save(ELEM / f"{name}.png")
        print("floor", name)

    for r, row in enumerate(PROP_NAMES, start=1):
        for c, name in enumerate(row):
            if name is None:
                continue
            cell = sheet.crop((c * CELL_W, r * CELL_H, (c + 1) * CELL_W, (r + 1) * CELL_H))
            prop = fit_prop(bleed_colors(remove_bg(cell)))
            prop.save(ELEM / f"{name}.png")
            print("prop ", name)

    gate = Image.open(OUT / "jungle_depths_gate_4x2.png").convert("RGB")
    g = bleed_colors(remove_bg(gate))
    bbox = g.getbbox()
    g = g.crop(bbox)
    scale = min(158 / g.width, 96 / g.height)
    g = g.resize((max(1, round(g.width * scale)), max(1, round(g.height * scale))), Image.LANCZOS)
    a = np.array(g)
    a[:, :, 3] = np.where(a[:, :, 3] >= 96, 255, 0)
    g = add_outline(Image.fromarray(a, "RGBA"))
    canvas = Image.new("RGBA", (160, 100), (0, 0, 0, 0))
    canvas.alpha_composite(g, ((160 - g.width) // 2, 100 - g.height))
    canvas.save(ELEM / "gate_ancient_tree.png")
    print("gate  gate_ancient_tree", g.size)


if __name__ == "__main__":
    main()
