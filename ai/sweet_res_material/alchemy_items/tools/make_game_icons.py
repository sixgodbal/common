import argparse
import os
from pathlib import Path

import numpy as np
from PIL import Image


def components(alpha):
    """4-connected components of the opaque mask."""
    h, w = alpha.shape
    seen = np.zeros((h, w), dtype=bool)
    result = []
    for y in range(h):
        for x in range(w):
            if alpha[y, x] == 0 or seen[y, x]:
                continue
            stack = [(y, x)]
            seen[y, x] = True
            pts = []
            while stack:
                cy, cx = stack.pop()
                pts.append((cy, cx))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < h and 0 <= nx < w and alpha[ny, nx] > 0 and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            result.append(pts)
    return result


def binary_alpha(img, threshold):
    arr = np.array(img)
    arr[:, :, 3] = np.where(arr[:, :, 3] >= threshold, 255, 0).astype(np.uint8)
    return Image.fromarray(arr, "RGBA")


def add_outline(img, color, min_component):
    arr = np.array(img)
    alpha = arr[:, :, 3]
    h, w = alpha.shape
    out = arr.copy()
    for pts in components(alpha):
        if len(pts) < min_component:
            continue
        for y, x in pts:
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = y + dy, x + dx
                if 0 <= ny < h and 0 <= nx < w and alpha[ny, nx] == 0:
                    out[ny, nx] = (color[0], color[1], color[2], 255)
    return Image.fromarray(out, "RGBA")


def main():
    ap = argparse.ArgumentParser(description="Downscale item icons to 45x45 game size with 1px outline.")
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=45)
    ap.add_argument("--threshold", type=int, default=110)
    ap.add_argument("--outline", default="26,26,32")
    ap.add_argument("--min-component", type=int, default=20)
    ap.add_argument("--preview-scale", type=int, default=8)
    args = ap.parse_args()

    src = Path(args.src)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    preview_dir = out.parent / f"preview_{args.preview_scale}x"
    preview_dir.mkdir(parents=True, exist_ok=True)

    color = tuple(int(c) for c in args.outline.split(","))
    files = sorted(p for p in src.glob("*.png"))
    if not files:
        raise SystemExit(f"no png found in {src}")

    for p in files:
        img = Image.open(p).convert("RGBA")
        small = img.resize((args.size, args.size), Image.Resampling.LANCZOS)
        small = binary_alpha(small, args.threshold)
        small = add_outline(small, color, args.min_component)
        small.save(out / p.name)
        small.resize(
            (args.size * args.preview_scale, args.size * args.preview_scale),
            Image.Resampling.NEAREST,
        ).save(preview_dir / p.name)
        print(f"OK  {p.name}")

    print(f"icons -> {out}")
    print(f"preview -> {preview_dir}")


if __name__ == "__main__":
    main()
