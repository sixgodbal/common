"""Preview processed 40px elements (8x nearest) and floor tiling tests."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"
ELEM = OUT / "elements"

FLOORS = ["floor_stone", "floor_moss", "floor_earth", "floor_water"]
PROPS = [
    ["wall_tree", "wall_bush", "wall_root", "wall_stump"],
    ["brick_log", "brick_sapling", "brick_bush", "brick_stump"],
    ["brick_snake", "wall_snake_totem", "wall_fern", None],
]

S = 8
CW, CH = 40 * S, 60 * S
PAD = 18
LABEL = 30
BG = (247, 241, 227)
INK = (54, 42, 30)


def checker(size, step=20):
    im = Image.new("RGB", size, (236, 232, 220))
    d = ImageDraw.Draw(im)
    for y in range(0, size[1], step):
        for x in range(0, size[0], step):
            if (x // step + y // step) % 2 == 0:
                d.rectangle([x, y, x + step - 1, y + step - 1], fill=(250, 247, 238))
    return im


try:
    font = ImageFont.truetype("msyh.ttc", 18)
except OSError:
    font = ImageFont.load_default()


def draw_cell(canvas, name, col, row, kind):
    x = PAD + col * (CW + PAD)
    y = PAD + row * (CH + LABEL + PAD)
    if name is None:
        return
    src = Image.open(ELEM / f"{name}.png").convert("RGBA")
    if kind == "floor":
        src = src.resize((40 * S, 40 * S), Image.NEAREST)
        tile = checker((40 * S, 40 * S), 20)
        tile.paste(src, (0, 0), src)
        canvas.paste(tile, (x, y + CH - 40 * S))
    else:
        src = src.resize((40 * S, 60 * S), Image.NEAREST)
        tile = checker((CW, CH), 20)
        tile.paste(src, (0, 0), src)
        canvas.paste(tile, (x, y))
    ImageDraw.Draw(canvas).text((x + 4, y + CH + 4), name, fill=INK, font=font)


def main():
    rows = 1 + len(PROPS)
    W = PAD + 4 * (CW + PAD)
    H = PAD + rows * (CH + LABEL + PAD)
    sheet = Image.new("RGB", (W, H), BG)
    for c, name in enumerate(FLOORS):
        draw_cell(sheet, name, c, 0, "floor")
    for r, row in enumerate(PROPS, start=1):
        for c, name in enumerate(row):
            draw_cell(sheet, name, c, r, "prop")
    sheet.save(OUT / "_elements_preview.png")
    print("OK", sheet.size)

    # floor tiling test: 6x6 tiles, 4x nearest
    T = 6
    for name in FLOORS:
        tile = Image.open(ELEM / f"{name}.png").convert("RGB")
        big = Image.new("RGB", (40 * T, 40 * T))
        for r in range(T):
            for c in range(T):
                big.paste(tile, (c * 40, r * 40))
        big.resize((40 * T * 4, 40 * T * 4), Image.NEAREST).save(OUT / f"_tiling_{name}.png")
    print("tiling tests OK")


if __name__ == "__main__":
    main()
