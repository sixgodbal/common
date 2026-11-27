"""Build a 40x40 jungle-depths layout guide for the AI concept map.

Cell values:
  0 floor       1 wall/tree      2 tree brick (destructible)
  3 gate (4x2)  4 water          5 spawn plaza       6 snake-accent brick
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw

N = 40
g = [[0] * N for _ in range(N)]


def rect(r0, c0, h, w, v):
    for r in range(r0, r0 + h):
        for c in range(c0, c0 + w):
            if 0 <= r < N and 0 <= c < N:
                g[r][c] = v


# ---- outer jungle wall (2 cells thick) ----
rect(0, 0, N, N, 1)
rect(2, 2, N - 4, N - 4, 0)

# ---- four spawn plazas ----
for r, c in ((4, 4), (4, 31), (31, 4), (31, 31)):
    rect(r, c, 5, 5, 5)

# ---- cross corridors (2 cells wide) ----
rect(2, 19, N - 4, 2, 0)
rect(19, 2, 2, N - 4, 0)

# ---- central gate plaza + 4x2 hollow ancient tree gate ----
rect(16, 16, 8, 8, 0)
rect(19, 18, 2, 4, 3)

# ---- water ponds (180-degree symmetric pair) ----
rect(10, 26, 4, 4, 4)
rect(26, 10, 4, 4, 4)

# ---- tree-brick clusters, 180-degree symmetric ----
brick_clusters = [(7, 12), (13, 7), (15, 15), (7, 26), (26, 7)]
for r, c in brick_clusters:
    rect(r, c, 2, 2, 2)
    rect(N - r - 2, N - c - 2, 2, 2, 2)

# ---- snake-accent bricks inside four clusters ----
for r, c in ((7, 12), (15, 15), (N - 8, N - 13), (N - 16, N - 16)):
    g[r][c] = 6

# ---- single tree props, 180-degree symmetric ----
for r, c in ((5, 14), (14, 5), (5, 25), (25, 5)):
    g[r][c] = 1
    g[N - r - 1][N - c - 1] = 1

# ---- a few root runs along the paths (soft cover) ----
for r, c in ((9, 17), (9, 22), (17, 9), (22, 9)):
    g[r][c] = 1
    g[N - r - 1][N - c - 1] = 1

# ---- spawn plazas stay open ----
for r, c in ((4, 4), (4, 31), (31, 4), (31, 31)):
    rect(r, c, 5, 5, 5)

colors = {
    0: (215, 230, 196),
    1: (47, 93, 58),
    2: (201, 138, 75),
    3: (142, 91, 181),
    4: (88, 169, 201),
    5: (255, 246, 216),
    6: (47, 168, 154),
}

CELL = 25
W = N * CELL
img = Image.new("RGB", (W, W), (255, 255, 255))
d = ImageDraw.Draw(img)
for r in range(N):
    for c in range(N):
        x, y = c * CELL, r * CELL
        d.rectangle([x, y, x + CELL - 2, y + CELL - 2], fill=colors[g[r][c]])

d.rectangle([0, 0, W - 1, W - 1], outline=(40, 40, 40), width=3)

out = Path(__file__).resolve().parents[1] / "out"
out.mkdir(parents=True, exist_ok=True)
img.save(out / "layout_40x40.png")

(out / "layout_40x40.json").write_text(
    json.dumps({"size": N, "grid": g}, ensure_ascii=False, separators=(",", ":")),
    encoding="utf-8",
)

counts = {}
for row in g:
    for v in row:
        counts[v] = counts.get(v, 0) + 1
print("saved", out / "layout_40x40.png", "cells:", counts)
