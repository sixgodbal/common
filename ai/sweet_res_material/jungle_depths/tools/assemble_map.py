"""Assemble the 40x40 jungle map from 40px elements, grid-exact."""

import json
from pathlib import Path

from PIL import Image, ImageDraw
from scipy import ndimage
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
ELEM = OUT / "elements"

N = 40
TILE = 40


def h(r, c, salt=0):
    return ((r * 73856093) ^ (c * 19349663) ^ (salt * 83492791)) & 0x7FFFFFFF


def load(name):
    return Image.open(ELEM / f"{name}.png").convert("RGBA")


def flip(tile, r, c):
    v = h(r, c, 7) % 4
    if v & 1:
        tile = tile.transpose(Image.FLIP_LEFT_RIGHT)
    if v & 2:
        tile = tile.transpose(Image.FLIP_TOP_BOTTOM)
    return tile


def main():
    data = json.loads((OUT / "layout_40x40.json").read_text(encoding="utf-8"))
    grid = data["grid"]
    g = np.array(grid)

    floors_old = {n: load(n) for n in ("floor_stone",)}
    grass = {n: load(f"floor2_{n}") for n in ("grass_plain", "grass_flowers", "grass_moss")}
    earth = {n: load(f"floor2_{n}") for n in ("earth_plain", "earth_leaves")}
    walls = {n: load(n) for n in ("wall_tree", "wall_bush", "wall_root", "wall_stump", "wall_fern", "wall_snake_totem")}
    bricks = {n: load(n) for n in ("brick_log", "brick_sapling", "brick_bush", "brick_stump")}
    snake_brick = load("brick_snake")
    gate = load("gate_ancient_tree")
    pond = load("pond_4x4_160")

    canvas = Image.new("RGBA", (N * TILE, N * TILE), (0, 0, 0, 0))

    # moss frames around spawn plazas and central plaza
    ring = set()
    for pr, pc in ((4, 4), (4, 31), (31, 4), (31, 31)):
        for r in range(pr - 1, pr + 6):
            for c in range(pc - 1, pc + 6):
                if 0 <= r < N and 0 <= c < N and not (pr <= r < pr + 5 and pc <= c < pc + 5):
                    ring.add((r, c))
    for r in range(15, 25):
        for c in range(15, 25):
            if not (16 <= r <= 23 and 16 <= c <= 23):
                ring.add((r, c))

    def near(r, c, values):
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if 0 <= rr < N and 0 <= cc < N and g[rr, cc] in values:
                    return True
        return False

    # ---- floors (everything except water) ----
    for r in range(N):
        for c in range(N):
            v = int(g[r, c])
            if v == 4:
                continue
            if v in (3, 5) or r in (19, 20) or c in (19, 20) or (16 <= r <= 23 and 16 <= c <= 23):
                tile = floors_old["floor_stone"]
            elif near(r, c, {4}):
                tile = flip(grass["grass_moss"], r, c)
            elif v in (2, 6) or near(r, c, {2, 6}):
                tile = flip(grass["grass_moss"], r, c)
            elif (r, c) in ring:
                tile = flip(grass["grass_flowers"], r, c)
            elif near(r, c, {1}):
                tile = flip(grass["grass_moss"], r, c)
            else:
                pick = h(r, c, 5) % 100
                if pick < 15:
                    tile = flip(grass["grass_flowers"], r, c)
                elif pick < 30:
                    tile = flip(grass["grass_moss"], r, c)
                else:
                    tile = flip(grass["grass_plain"], r, c)
            canvas.alpha_composite(tile, (c * TILE, r * TILE))

    # ---- ponds: paste a continuous 4x4 texture, then draw a 1px bank ----
    water = g == 4
    lbl, n = ndimage.label(water)
    d = ImageDraw.Draw(canvas)
    for i in range(1, n + 1):
        ys, xs = np.where(lbl == i)
        r0, r1, c0, c1 = ys.min(), ys.max(), xs.min(), xs.max()
        x0, y0 = int(c0 * TILE), int(r0 * TILE)
        w, hgt = int((c1 - c0 + 1) * TILE), int((r1 - r0 + 1) * TILE)
        tex = pond if (i % 2 == 1) else pond.transpose(Image.FLIP_LEFT_RIGHT)
        canvas.alpha_composite(tex.resize((w, hgt), Image.LANCZOS), (x0, y0))
        d.rectangle([x0 - 1, y0 - 1, x0 + w, y0 + hgt], outline=(58, 79, 46, 255), width=1)

    # ---- props, top row to bottom so nearer props overlap ----
    for r in range(N):
        for c in range(N):
            v = int(g[r, c])
            if v == 1:
                roll = h(r, c, 2) % 100
                border = r < 2 or r >= N - 2 or c < 2 or c >= N - 2
                if (r, c) == (9, 17):
                    sprite = walls["wall_snake_totem"]
                elif border:
                    if roll < 62:
                        sprite = walls["wall_bush"]
                    elif roll < 84:
                        sprite = walls["wall_tree"]
                    elif roll < 94:
                        sprite = walls["wall_root"]
                    else:
                        sprite = walls["wall_fern"]
                elif roll < 50:
                    sprite = walls["wall_tree"]
                elif roll < 72:
                    sprite = walls["wall_bush"]
                elif roll < 86:
                    sprite = walls["wall_root"]
                elif roll < 95:
                    sprite = walls["wall_stump"]
                else:
                    sprite = walls["wall_fern"]
                canvas.alpha_composite(sprite, (c * TILE, (r + 1) * TILE - sprite.height))
            elif v == 2:
                roll = h(r, c, 3) % 100
                if roll < 30:
                    sprite = bricks["brick_log"]
                elif roll < 58:
                    sprite = bricks["brick_sapling"]
                elif roll < 80:
                    sprite = bricks["brick_bush"]
                else:
                    sprite = bricks["brick_stump"]
                canvas.alpha_composite(sprite, (c * TILE, (r + 1) * TILE - sprite.height))
            elif v == 6:
                canvas.alpha_composite(snake_brick, (c * TILE, (r + 1) * TILE - snake_brick.height))

    # ---- 4x2 gate ----
    canvas.alpha_composite(gate, (18 * TILE, 21 * TILE - gate.height))

    canvas.convert("RGB").save(OUT / "map_40x40_assembled.png")
    canvas.convert("RGB").resize((N * TILE * 2, N * TILE * 2), Image.NEAREST).save(
        OUT / "map_40x40_assembled_2x.png"
    )
    print("OK", canvas.size, "->", OUT / "map_40x40_assembled.png")


if __name__ == "__main__":
    main()
