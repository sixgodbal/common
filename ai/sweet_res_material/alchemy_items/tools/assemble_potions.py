import argparse
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image


def cut_background(img, tol=42):
    """Flood fill the flat cream background from the borders."""
    img = img.convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3].astype(np.int16)
    ref = rgb[2, 2].copy()
    bg = np.zeros((h, w), dtype=bool)
    q = deque()

    def try_push(y, x):
        if bg[y, x]:
            return
        d = int(np.abs(rgb[y, x] - ref).sum())
        if d <= tol:
            bg[y, x] = True
            q.append((y, x))

    for x in range(w):
        try_push(0, x)
        try_push(h - 1, x)
    for y in range(h):
        try_push(y, 0)
        try_push(y, w - 1)

    while q:
        y, x = q.popleft()
        if y > 0:
            try_push(y - 1, x)
        if y < h - 1:
            try_push(y + 1, x)
        if x > 0:
            try_push(y, x - 1)
        if x < w - 1:
            try_push(y, x + 1)

    arr[bg, 3] = 0
    return Image.fromarray(arr, "RGBA")


def content_bbox(img, thr=8):
    a = np.array(img)[:, :, 3]
    ys, xs = np.where(a > thr)
    if len(xs) == 0:
        return None
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def fit(img, box, target_h, cell=256, bottom_margin=10, max_w=244):
    crop = img.crop(box)
    cw, ch = crop.size
    scale = min(target_h / ch, max_w / cw)
    nw, nh = max(1, round(cw * scale)), max(1, round(ch * scale))
    crop = crop.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (cell, cell), (0, 0, 0, 0))
    canvas.alpha_composite(crop, ((cell - nw) // 2, cell - bottom_margin - nh))
    # binary alpha for clean game edges
    arr = np.array(canvas)
    arr[:, :, 3] = np.where(arr[:, :, 3] >= 110, 255, 0).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--small", required=True)
    ap.add_argument("--medium", required=True)
    ap.add_argument("--large", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--heights", default="184,210,236")
    args = ap.parse_args()

    out = Path(args.out)
    icons = out / "icons_256"
    icons.mkdir(parents=True, exist_ok=True)

    heights = [int(h) for h in args.heights.split(",")]
    sheets = [args.small, args.medium, args.large]
    tiers = ["small", "medium", "large"]
    colors = ["red", "blue", "green", "gold"]

    sheet = Image.new("RGBA", (1024, 768), (247, 241, 227, 255))

    for r, path in enumerate(sheets):
        img = cut_background(Image.open(path))
        cw, ch = img.size[0] // 2, img.size[1] // 2
        for c in range(4):
            cx, cy = (c % 2) * cw, (c // 2) * ch
            cell = img.crop((cx, cy, cx + cw, cy + ch))
            box = content_bbox(cell)
            if box is None:
                print(f"MISS {tiers[r]} {colors[c]}")
                continue
            icon = fit(cell, box, heights[r])
            name = f"potion_{tiers[r]}_{colors[c]}"
            icon.save(icons / f"{name}.png")
            sheet.alpha_composite(icon, (c * 256, r * 256))
            print(f"OK  {name}.png")

    sheet_path = out / "potion_sheet_1024x768.png"
    sheet.save(sheet_path)
    print("sheet ->", sheet_path)


if __name__ == "__main__":
    main()
