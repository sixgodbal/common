import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def build_master(cell, d0, d1, gamma):
    arr = np.array(cell).astype(np.float32)
    rgb = arr[:, :, :3]
    cream = np.array([247, 241, 227], dtype=np.float32)
    d = np.sqrt(((rgb - cream) ** 2).sum(axis=2))
    a = np.clip((d - d0) / (d1 - d0), 0, 1) ** gamma
    a[a < 0.02] = 0
    arr[:, :, 3] = a * 255
    return Image.fromarray(arr.astype(np.uint8), "RGBA"), arr, d


def main():
    ap = argparse.ArgumentParser(description="Crop one glow icon cell and export 256/45/142.")
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--row", type=int, default=1)
    ap.add_argument("--col", type=int, default=2)
    ap.add_argument("--cols", type=int, default=5)
    ap.add_argument("--rows", type=int, default=3)
    ap.add_argument("--name", default="lycoris_glow")
    ap.add_argument("--d0", type=float, default=14)
    ap.add_argument("--d1", type=float, default=75)
    ap.add_argument("--gamma", type=float, default=0.8)
    ap.add_argument("--solid45", type=float, default=110, help="45px binary alpha threshold; 0 disables")
    args = ap.parse_args()

    src = Image.open(args.src).convert("RGBA")
    cw, ch = src.width // args.cols, src.height // args.rows
    cell = src.crop((args.col * cw, args.row * ch, (args.col + 1) * cw, (args.row + 1) * ch))

    master, arr, d = build_master(cell, args.d0, args.d1, args.gamma)

    out = Path(args.out)
    for size in (256, 45, 142):
        ddir = out / f"icons_{size}"
        ddir.mkdir(parents=True, exist_ok=True)
        if size == 45 and args.solid45 > 0:
            solid = arr.copy()
            solid[:, :, 3] = np.where(d > args.solid45, 255, 0).astype(np.uint8)
            im = Image.fromarray(solid.astype(np.uint8), "RGBA").resize((45, 45), Image.Resampling.LANCZOS)
        else:
            im = master if size == 256 else master.resize((size, size), Image.Resampling.LANCZOS)
        im.save(ddir / f"{args.name}.png")
        print(f"OK  icons_{size}/{args.name}.png")

    panels = []
    for size, scale, label in ((45, 8, "45 x 45 (8x)"), (142, 2, "142 x 142 (2x)"), (256, 1.5, "256 x 256 (1.5x)")):
        if size == 45 and args.solid45 > 0:
            solid = arr.copy()
            solid[:, :, 3] = np.where(d > args.solid45, 255, 0).astype(np.uint8)
            im = Image.fromarray(solid.astype(np.uint8), "RGBA").resize((45, 45), Image.Resampling.LANCZOS)
        else:
            im = master if size == 256 else master.resize((size, size), Image.Resampling.LANCZOS)
        px = int(size * scale)
        panels.append((im.resize((px, px), Image.Resampling.NEAREST), label, px))

    pad = 18
    head = 46
    W = pad + sum(p[2] + pad for p in panels)
    H = head + max(p[2] for p in panels) + 42
    sheet = Image.new("RGBA", (W, H), (246, 240, 228, 255))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)
    except Exception:
        font = None
    x = pad
    for im, label, px in panels:
        bg = Image.new("RGBA", (px, px), (0, 0, 0, 0))
        bg.alpha_composite(im)
        sheet.alpha_composite(bg, (x, head))
        draw.text((x, head - 26), label, fill=(40, 30, 20, 255), font=font)
        x += px + pad
    sheet.save(out / "_preview.png")
    print("preview ->", out / "_preview.png")


if __name__ == "__main__":
    main()
