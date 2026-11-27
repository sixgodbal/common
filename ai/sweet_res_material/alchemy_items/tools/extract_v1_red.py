import argparse
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image


def cut_background(img, tol=42):
    img = img.convert("RGBA")
    arr = np.array(img)
    h, w = arr.shape[:2]
    rgb = arr[:, :, :3].astype(np.int16)
    ref = rgb[2, 2].copy()
    bg = np.zeros((h, w), dtype=bool)
    q = deque()

    def push(y, x):
        if bg[y, x]:
            return
        if int(np.abs(rgb[y, x] - ref).sum()) <= tol:
            bg[y, x] = True
            q.append((y, x))

    for x in range(w):
        push(0, x)
        push(h - 1, x)
    for y in range(h):
        push(y, 0)
        push(y, w - 1)
    while q:
        y, x = q.popleft()
        if y > 0:
            push(y - 1, x)
        if y < h - 1:
            push(y + 1, x)
        if x > 0:
            push(y, x - 1)
        if x < w - 1:
            push(y, x + 1)

    arr[bg, 3] = 0
    return Image.fromarray(arr, "RGBA")


def bbox(img, thr=8):
    a = np.array(img)[:, :, 3]
    ys, xs = np.where(a > thr)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--col", type=int, default=0)
    ap.add_argument("--cell", type=int, default=256)
    ap.add_argument("--max-height", type=int, default=236)
    ap.add_argument("--max-width", type=int, default=244)
    ap.add_argument("--bottom-margin", type=int, default=10)
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    img = cut_background(Image.open(args.sheet))
    cw, ch = img.size[0] // 4, img.size[1] // 3
    tiers = ["small", "medium", "large"]

    crops = []
    for r in range(3):
        cell = img.crop((args.col * cw, r * ch, (args.col + 1) * cw, (r + 1) * ch))
        box = bbox(cell)
        crops.append((tiers[r], cell.crop(box)))

    max_w = max(c.size[0] for _, c in crops)
    max_h = max(c.size[1] for _, c in crops)
    scale = min(args.max_height / max_h, args.max_width / max_w)

    for tier, crop in crops:
        nw = max(1, round(crop.size[0] * scale))
        nh = max(1, round(crop.size[1] * scale))
        resized = crop.resize((nw, nh), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (args.cell, args.cell), (0, 0, 0, 0))
        canvas.alpha_composite(resized, ((args.cell - nw) // 2, args.cell - args.bottom_margin - nh))
        arr = np.array(canvas)
        arr[:, :, 3] = np.where(arr[:, :, 3] >= 110, 255, 0).astype(np.uint8)
        name = f"potion_{tier}_red_v1.png"
        Image.fromarray(arr, "RGBA").save(out / name)
        print(f"OK  {name}  ({nw}x{nh} placed)")


if __name__ == "__main__":
    main()
