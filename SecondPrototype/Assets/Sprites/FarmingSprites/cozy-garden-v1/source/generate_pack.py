#!/usr/bin/env python3
"""Build the original, deterministic Cozy Garden 32x32 pixel-art pack.

Requires Pillow. Run ``python3 source/generate_pack.py`` to rebuild, or pass
``--check`` to audit the current export without changing it.
"""

from __future__ import annotations

import json
import math
import sys
from collections import deque
from pathlib import Path
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SIZE = 32
SCALE = 3
TRANSPARENT = (0, 0, 0, 0)

# A shared 36-colour ink-and-pigment palette plus transparent.
P = {
    "ink": "#342F3D",
    "ink_soft": "#514458",
    "bark_dark": "#604338",
    "bark": "#825743",
    "bark_light": "#AE7753",
    "leaf_dark": "#3F6247",
    "leaf": "#57835A",
    "leaf_bright": "#7BA46B",
    "leaf_pale": "#A6BD78",
    "grass_dark": "#628860",
    "grass": "#80A46F",
    "grass_light": "#9DBD7C",
    "moss": "#B6BC7A",
    "earth_dark": "#704B44",
    "earth": "#94624C",
    "earth_light": "#B87B55",
    "earth_gold": "#D6A06A",
    "stone_dark": "#6C7372",
    "stone": "#8D9690",
    "stone_light": "#B1B5A0",
    "stone_glow": "#D7CDAE",
    "water_dark": "#467B89",
    "water": "#5F9EA3",
    "water_light": "#88C0B1",
    "water_glow": "#BEDAB6",
    "cream": "#F2E4C0",
    "sun": "#E6B85C",
    "coral": "#D26E61",
    "coral_light": "#E8957D",
    "lavender": "#9581AB",
    "lavender_light": "#B5A0C0",
    "sky": "#6B92B7",
    "sky_light": "#A7C3C0",
    "carrot": "#E27D49",
    "tomato": "#C95650",
    "tomato_light": "#E47C68",
}


def rgba(value: str) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4)) + (255,)  # type: ignore[return-value]


C = {name: rgba(value) for name, value in P.items()}

# Export checks enforce upper-left light, lower-right shade, and reserve
# near-black outlines for structure sprites.
SHADING_RULE = {"light": "upper-left", "shade": "lower-right", "near_black_ink": "structures only"}
OBJECT_FOLDERS = {"trees", "structures", "flowers", "crops", "props", "critters"}
NEAR_BLACK_OUTLINE_SWATCHES = {C["ink"], C["ink_soft"]}
LIGHT_SWATCHES = {color for color in C.values()
                  if (299 * color[0] + 587 * color[1] + 114 * color[2]) // 1000 >= 170}
SHADE_SWATCHES = {color for color in C.values()
                  if (299 * color[0] + 587 * color[1] + 114 * color[2]) // 1000 <= 130}

# Ripple rectangles are (dx, dy, width, height, swatch), offset from the water
# centre. Each mask selects a fixed layout by mask modulo four: exactly three
# deliberate marks per tile, with no random placement.
RIPPLE_LAYOUTS = (
    ((-6, -5, 4, 1, "water_light"), (3, -1, 3, 1, "water_glow"), (-1, 5, 2, 1, "water_light")),
    ((-7, 2, 3, 1, "water_light"), (2, -6, 4, 1, "water_glow"), (4, 4, 2, 1, "water_light")),
    ((-3, -7, 3, 1, "water_glow"), (5, 0, 3, 1, "water_light"), (-7, 4, 4, 1, "water_light")),
    ((-5, -2, 4, 1, "water_light"), (1, -7, 2, 1, "water_glow"), (3, 5, 3, 1, "water_light")),
)

GRASS_DENSITY = {
    "meadow": "sparse", "clover": "medium", "blossom": "medium", "moss": "dense",
    "sprigs": "sparse", "leafy": "medium",
}
GRASS_VARIANTS = tuple(GRASS_DENSITY)

# Each water mask selects one of three silhouettes and a fixed quarter-turn.
# The sequence cycles shapes every mask and rotates after each group of three.
REFLECTION_SHAPES = {
    "lens": ((2, 0), (3, 0), (4, 0), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (5, 2), (6, 2)),
    "sweep": ((0, 0), (1, 0), (2, 0), (3, 0), (2, 1), (3, 1), (4, 1), (5, 1), (4, 2), (5, 2), (6, 2)),
    "broken": ((1, 0), (2, 0), (3, 0), (4, 0), (5, 0), (0, 1), (1, 1), (2, 1), (4, 1), (5, 1), (6, 1), (1, 2), (2, 2), (3, 2), (4, 2), (5, 2)),
}
REFLECTION_NAMES = tuple(REFLECTION_SHAPES)
REFLECTION_MASK_MAP = tuple((mask % len(REFLECTION_NAMES), (mask // len(REFLECTION_NAMES)) % 4)
                            for mask in range(16))

# Four fixed, mask-indexed surface layouts keep the path grain and pebble flecks
# deterministic while breaking up any long horizontal or vertical bands.
PATH_SURFACE_LAYOUTS = (
    ((-4, -2, 2, 1, "earth_light"), (1, -3, 1, 1, "earth_gold"),
     (3, 1, 2, 1, "earth_dark"), (-1, 3, 1, 1, "earth_light")),
    ((-3, 2, 2, 1, "earth_dark"), (2, -4, 2, 1, "earth_light"),
     (-1, -1, 1, 1, "earth_gold"), (3, 3, 1, 1, "earth_light")),
    ((-4, 1, 1, 1, "earth_gold"), (0, -3, 2, 1, "earth_dark"),
     (2, 2, 2, 1, "earth_light"), (-2, -1, 1, 1, "earth_light")),
    ((-2, -4, 2, 1, "earth_light"), (3, -1, 1, 1, "earth_gold"),
     (-3, 2, 2, 1, "earth_dark"), (1, 3, 1, 1, "earth_light")),
)
PATH_COLORS = {C[name] for name in ("bark", "earth", "earth_dark", "earth_light", "earth_gold")}


def new_tile(background: str | None = None) -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), C[background] if background else TRANSPARENT)
    return image


def box(draw: ImageDraw.ImageDraw, coords: tuple[int, int, int, int], color: str | tuple[int, int, int, int]) -> None:
    draw.rectangle(coords, fill=C[color] if isinstance(color, str) else color)


def line(draw: ImageDraw.ImageDraw, coords: tuple[int, ...], color: str, width: int = 1) -> None:
    draw.line(coords, fill=C[color], width=width)


def polygon(draw: ImageDraw.ImageDraw, points: list[tuple[int, int]], color: str) -> None:
    draw.polygon(points, fill=C[color])


def ellipse(draw: ImageDraw.ImageDraw, coords: tuple[int, int, int, int], color: str) -> None:
    draw.ellipse(coords, fill=C[color])


def pxtext(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, color: str, scale: int = 1) -> int:
    """Tiny bundled 3x5 pixel font, so sheets need no external font file."""
    glyphs = {
        "A": ("010", "101", "111", "101", "101"), "B": ("110", "101", "110", "101", "110"),
        "C": ("011", "100", "100", "100", "011"), "D": ("110", "101", "101", "101", "110"),
        "E": ("111", "100", "110", "100", "111"), "F": ("111", "100", "110", "100", "100"),
        "G": ("011", "100", "101", "101", "011"), "H": ("101", "101", "111", "101", "101"),
        "I": ("111", "010", "010", "010", "111"), "J": ("001", "001", "001", "101", "010"),
        "K": ("101", "101", "110", "101", "101"), "L": ("100", "100", "100", "100", "111"),
        "M": ("101", "111", "111", "101", "101"), "N": ("101", "111", "111", "111", "101"),
        "O": ("010", "101", "101", "101", "010"), "P": ("110", "101", "110", "100", "100"),
        "Q": ("010", "101", "101", "111", "011"), "R": ("110", "101", "110", "101", "101"),
        "S": ("011", "100", "010", "001", "110"), "T": ("111", "010", "010", "010", "010"),
        "U": ("101", "101", "101", "101", "111"), "V": ("101", "101", "101", "101", "010"),
        "W": ("101", "101", "111", "111", "101"), "X": ("101", "101", "010", "101", "101"),
        "Y": ("101", "101", "010", "010", "010"), "Z": ("111", "001", "010", "100", "111"),
        "0": ("111", "101", "101", "101", "111"), "1": ("010", "110", "010", "010", "111"),
        "2": ("110", "001", "010", "100", "111"), "3": ("110", "001", "010", "001", "110"),
        "4": ("101", "101", "111", "001", "001"), "5": ("111", "100", "110", "001", "110"),
        "6": ("011", "100", "110", "101", "010"), "7": ("111", "001", "010", "010", "010"),
        "8": ("010", "101", "010", "101", "010"), "9": ("010", "101", "011", "001", "110"),
        "_": ("000", "000", "000", "000", "111"), "-": ("000", "000", "111", "000", "000"),
        "/": ("001", "001", "010", "100", "100"), ".": ("000", "000", "000", "000", "010"),
        ":": ("000", "010", "000", "010", "000"), "#": ("101", "111", "101", "111", "101"),
        " ": ("000", "000", "000", "000", "000"),
    }
    d = draw
    cursor = x
    for char in text.upper():
        bitmap = glyphs.get(char, glyphs["-"])
        for gy, row in enumerate(bitmap):
            for gx, cell in enumerate(row):
                if cell == "1":
                    d.rectangle((cursor + gx * scale, y + gy * scale,
                                 cursor + (gx + 1) * scale - 1, y + (gy + 1) * scale - 1), fill=C[color])
        cursor += 4 * scale
    return cursor - x


def save_tile(rel_path: str, image: Image.Image, category: str, pivot: str = "center", collision: str = "none") -> dict:
    path = ASSETS / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if image.size != (SIZE, SIZE):
        raise ValueError(f"sprite {rel_path} is {image.size}, expected 32x32")
    image.save(path, format="PNG", optimize=False)
    return {"name": path.stem, "path": rel_path.replace("\\", "/"), "category": category,
            "pivot": pivot, "collision": collision}


def grass_tile(kind: str) -> Image.Image:
    im = new_tile("grass")
    d = ImageDraw.Draw(im)
    # Ground accents are small composed tufts, spaced to stay calm at native size.
    def tuft(x: int, y: int) -> None:
        box(d, (x, y + 2, x + 1, y + 3), "grass_dark")
        box(d, (x + 1, y + 1, x + 2, y + 2), "grass_light")
        box(d, (x + 2, y, x + 3, y + 1), "grass_light")
        box(d, (x + 3, y + 2, x + 4, y + 3), "grass_dark")
    if kind == "meadow":
        for x, y in ((3, 5), (22, 8), (14, 23)):
            tuft(x, y)
    elif kind == "clover":
        # Three rounded leaflets share one short stem, so these read as clover
        # heads instead of separate upright marks.
        for x, y in ((4, 8), (21, 6)):
            ellipse(d, (x, y + 1, x + 3, y + 4), "leaf_bright")
            ellipse(d, (x + 2, y, x + 5, y + 3), "leaf_pale")
            ellipse(d, (x + 4, y + 1, x + 7, y + 4), "leaf_bright")
            line(d, (x + 3, y + 3, x + 3, y + 5), "leaf_dark")
            box(d, (x + 2, y + 2, x + 2, y + 2), "leaf_pale")
        tuft(14, 23)
    elif kind == "blossom":
        for x, y in ((6, 6), (23, 12), (13, 24)):
            box(d, (x, y, x + 1, y + 1), "cream")
            box(d, (x + 1, y + 1, x + 2, y + 2), "sun")
            box(d, (x - 1, y + 1, x, y + 2), "cream")
            box(d, (x + 3, y + 3, x + 4, y + 4), "grass_dark")
        for x, y in ((15, 5), (3, 21)):
            tuft(x, y)
    elif kind == "moss":  # mossy, softly shaded patches with grassy satellites
        for pts in (((2, 8), (7, 6), (12, 8), (11, 11), (5, 12)),
                    ((18, 19), (22, 16), (28, 18), (29, 22), (23, 24), (19, 22))):
            polygon(d, list(pts), "moss")
            box(d, (pts[0][0] + 2, pts[0][1] + 2, pts[0][0] + 5, pts[0][1] + 2), "leaf_pale")
        for x, y in ((1, 9), (12, 9), (19, 18), (28, 23), (24, 25)):
            box(d, (x, y, x + 1, y), "moss")
        for x, y in ((3, 6), (10, 12), (20, 17), (27, 24)):
            box(d, (x, y, x, y), "grass_light")
        tuft(14, 4)
    elif kind == "sprigs":
        for x, y in ((4, 6), (20, 10), (12, 24)):
            line(d, (x + 2, y + 5, x + 2, y + 1), "leaf_dark")
            ellipse(d, (x, y + 1, x + 2, y + 3), "leaf_bright")
            ellipse(d, (x + 2, y, x + 4, y + 2), "leaf_pale")
            ellipse(d, (x + 3, y + 2, x + 5, y + 4), "leaf")
            box(d, (x + 1, y + 4, x + 3, y + 4), "grass_dark")
    elif kind == "leafy":
        for x, y in ((3, 7), (19, 5), (23, 21), (7, 23)):
            ellipse(d, (x, y + 1, x + 3, y + 3), "leaf")
            ellipse(d, (x + 2, y, x + 5, y + 2), "leaf_bright")
            box(d, (x + 2, y + 2, x + 3, y + 2), "leaf_dark")
        tuft(13, 14)
    else:
        raise ValueError(f"unknown grass arrangement: {kind}")
    return im


def soil_tile(kind: str) -> Image.Image:
    im = new_tile("earth")
    d = ImageDraw.Draw(im)
    # Broken furrows vary in row spacing, run length and gaps while retaining
    # the upper-left light and lower-right shadow of the tilled earth.
    furrows = (
        (5, ((2, 9), (13, 19), (23, 29)), ((4, 8), (15, 18), (25, 28))),
        (12, ((4, 15), (19, 27)), ((6, 11), (21, 25))),
        (20, ((1, 6), (10, 18), (22, 30)), ((3, 5), (12, 16), (24, 28))),
        (28, ((3, 13), (17, 23), (27, 30)), ((5, 10), (19, 22), (28, 29))),
    )
    for y, shadow_spans, light_spans in furrows:
        for x1, x2 in shadow_spans:
            line(d, (x1, y, x2, y + (1 if (x1 + y) % 3 == 0 else 0)), "earth_dark", 1)
        for x1, x2 in light_spans:
            line(d, (x1, y - 2, x2, y - 2), "earth_light", 1)
    for x, y in ((7, 7), (25, 14), (15, 22), (4, 26), (20, 6)):
        box(d, (x, y, x + (1 if x % 2 else 0), y), "earth_gold")
    if kind == "wet":
        # Broader, broken blue damp clumps make the wet bed read at a glance.
        for pts in (((4, 8), (8, 7), (10, 9), (8, 10), (5, 10)),
                    ((21, 15), (25, 15), (27, 17), (24, 18), (21, 17)),
                    ((10, 25), (13, 24), (16, 26), (14, 28), (11, 27))):
            polygon(d, list(pts), "water_dark")
        for x, y in ((6, 8), (23, 16), (12, 25)):
            box(d, (x, y, x + 1, y), "water_light")
    elif kind == "seeded":
        for x, y in ((7, 7), (23, 15), (14, 23)):
            box(d, (x, y, x + 2, y + 1), "earth_dark")
            box(d, (x, y - 2, x, y - 1), "leaf")
    elif kind == "raised":
        box(d, (1, 2, 30, 5), "bark_dark")
        box(d, (1, 2, 30, 3), "bark_light")
        box(d, (1, 26, 30, 29), "bark_dark")
        box(d, (1, 26, 30, 27), "bark")
        box(d, (2, 6, 4, 25), "bark_dark")
        box(d, (2, 6, 3, 25), "bark_light")
        box(d, (27, 6, 29, 25), "bark_dark")
        box(d, (27, 6, 28, 25), "bark")
    return im


def path_region(mask: int) -> set[tuple[int, int]]:
    """Build one connected, gently wobbled earth shape for a four-way mask."""
    region: set[tuple[int, int]] = set()
    # An octagonal hub gives turns and junctions bevelled, softer corners.
    for y in range(10, 22):
        for x in range(10, 22):
            clipped_corner = ((x <= 11 and y <= 11) or (x >= 20 and y <= 11) or
                              (x <= 11 and y >= 20) or (x >= 20 and y >= 20))
            if not clipped_corner:
                region.add((x, y))

    half_width = (4, 4, 5, 4, 4, 3, 4, 5, 4, 3, 4, 4, 5, 4, 4, 4)
    center_shift = (0, 0, 1, 0, -1, 0, 1, 0, 0, -1, 0, 1, 0, 0, 0, 0)
    if mask & 1:
        for y in range(16):
            center = 15 + center_shift[y]
            region.update((x, y) for x in range(center - half_width[y], center + half_width[y] + 1))
    if mask & 2:
        for x in range(16, SIZE):
            index = x - 16
            center = 15 + center_shift[index]
            region.update((x, y) for y in range(center - half_width[index], center + half_width[index] + 1))
    if mask & 4:
        for y in range(16, SIZE):
            index = y - 16
            center = 15 + center_shift[index]
            region.update((x, y) for x in range(center - half_width[index], center + half_width[index] + 1))
    if mask & 8:
        for x in range(16):
            center = 15 + center_shift[x]
            region.update((x, y) for y in range(center - half_width[x], center + half_width[x] + 1))
    return region


def path_tile(mask: int) -> Image.Image:
    im = grass_tile("meadow")
    d = ImageDraw.Draw(im)
    cx = cy = 15
    region = path_region(mask)
    outline = {(x + dx, y + dy) for x, y in region
               for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
               if 0 <= x + dx < SIZE and 0 <= y + dy < SIZE and (x + dx, y + dy) not in region}
    # Bark is a muted, lighter outline than the former dark stripe treatment.
    for x, y in outline:
        box(d, (x, y, x, y), "bark")
    for x, y in region:
        box(d, (x, y, x, y), "earth")
        if (x - 1, y) not in region or (x, y - 1) not in region:
            if (x + 2 * y) % 4 != 0:
                box(d, (x, y, x, y), "earth_light")
        elif ((x + 1, y) not in region or (x, y + 1) not in region) and (x + y) % 5 == 0:
            box(d, (x, y, x, y), "earth_dark")

    # A few hand-placed surface flecks and tiny bevelled pebble pairs interrupt
    # the earth without building another directional band.
    for dx, dy, width, height, color in PATH_SURFACE_LAYOUTS[mask % len(PATH_SURFACE_LAYOUTS)]:
        for y in range(cy + dy, cy + dy + height):
            for x in range(cx + dx, cx + dx + width):
                if (x, y) in region:
                    box(d, (x, y, x, y), color)
    pebble_layouts = (((-3, 1), (3, -2)), ((1, 3), (-4, -2)),
                      ((-2, -3), (3, 2)), ((-4, 2), (2, -3)))
    for dx, dy in pebble_layouts[mask % len(pebble_layouts)]:
        x, y = cx + dx, cy + dy
        if all((px, py) in region for px, py in ((x, y), (x + 1, y), (x + 2, y), (x + 1, y + 1))):
            ellipse(d, (x, y, x + 2, y + 1), "earth_light")
            box(d, (x + 1, y + 1, x + 2, y + 1), "earth_dark")

    # Grass nibbles sit just inside the path shoulder; the tile-edge throat
    # stays broad and continuous for every connected side.
    nicks = {1: ((12, 4), (19, 8)), 2: ((24, 12), (28, 19)),
             4: ((12, 24), (19, 28)), 8: ((4, 12), (8, 19))}
    for bit in (1, 2, 4, 8):
        if mask & bit:
            for x, y in nicks[bit]:
                box(d, (x, y, x, y), "grass")
    return im


def water_tile(mask: int) -> Image.Image:
    im = grass_tile("meadow")
    d = ImageDraw.Draw(im)
    n, e, s, w = bool(mask & 1), bool(mask & 2), bool(mask & 4), bool(mask & 8)
    # Exposed sides get a broken, stepped sand bank. Connected sides reach the
    # tile edge, so joined water does not form orange seams between cells.
    l, r = (0 if w else 5), (31 if e else 26)
    t, b = (0 if n else 5), (31 if s else 26)
    mx, my = (l + r) // 2, (t + b) // 2
    if not n:
        polygon(d, [(l - 2, 0), (r + 2, 0), (r + 2, 2), (r, 3), (mx + 5, 2),
                    (mx + 2, 4), (mx - 2, 3), (l + 3, 4), (l + 1, 2)], "earth")
        box(d, (mx - 4, 3, mx - 2, 3), "earth_light")
    if not e:
        polygon(d, [(31, t - 2), (31, b + 2), (29, b + 2), (28, b), (29, my + 5),
                    (27, my + 2), (28, my - 2), (27, t + 3), (29, t + 1)], "earth")
        box(d, (28, my - 4, 28, my - 2), "earth_light")
    if not s:
        polygon(d, [(r + 2, 31), (l - 2, 31), (l - 2, 29), (l, 28), (mx - 5, 29),
                    (mx - 2, 27), (mx + 2, 28), (r - 3, 27), (r - 1, 29)], "earth")
        box(d, (mx + 2, 28, mx + 4, 28), "earth_light")
    if not w:
        polygon(d, [(0, b + 2), (0, t - 2), (2, t - 2), (3, t), (2, my - 5),
                    (4, my - 2), (3, my + 2), (4, b - 3), (2, b - 1)], "earth")
        box(d, (3, my + 2, 3, my + 4), "earth_light")

    def shore_shape(left: int, top: int, right: int, bottom: int, inset_radius: int = 3) -> list[tuple[int, int]]:
        # Corner chamfers vary in a fixed 3–5px rhythm according to the mask.
        cut_tl = inset_radius + (mask % 3) if not n and not w else 0
        cut_tr = inset_radius + ((mask + 1) % 3) if not n and not e else 0
        cut_br = inset_radius + ((mask + 2) % 3) if not s and not e else 0
        cut_bl = inset_radius + ((mask + 1) % 3) if not s and not w else 0
        return [(left + cut_tl, top), (right - cut_tr, top), (right, top + cut_tr),
                (right, bottom - cut_br), (right - cut_br, bottom), (left + cut_bl, bottom),
                (left, bottom - cut_bl), (left, top + cut_tl)]

    # The outer shallows, mid-water and dark centre make depth legible at 32px.
    polygon(d, shore_shape(l, t, r, b), "water_light")
    il, ir = (0 if w else l + 2), (31 if e else r - 2)
    it, ib = (0 if n else t + 2), (31 if s else b - 2)
    polygon(d, shore_shape(il, it, ir, ib, 2), "water")

    # Mid-tone water reaches into a few fixed shallow patches near the exposed
    # shore, giving the bank a softer, less stamped boundary.
    if not n:
        box(d, (mx - 5, t + 1, mx - 4, t + 1), "water")
        box(d, (mx + 6, t + 2, mx + 7, t + 2), "water")
    if not e:
        box(d, (r - 1, my - 5, r - 1, my - 4), "water")
        box(d, (r - 2, my + 5, r - 2, my + 6), "water")
    if not s:
        box(d, (mx + 4, b - 1, mx + 5, b - 1), "water")
        box(d, (mx - 7, b - 2, mx - 6, b - 2), "water")
    if not w:
        box(d, (l + 1, my + 4, l + 1, my + 5), "water")
        box(d, (l + 2, my - 6, l + 2, my - 5), "water")

    # The dark reflection is a distinct mask-mapped silhouette with a fixed
    # quarter-turn; the mapping is exported in tileset-sheet-map.json.
    shape_index, rotation = REFLECTION_MASK_MAP[mask]
    points = list(REFLECTION_SHAPES[REFLECTION_NAMES[shape_index]])
    shape_width, shape_height = 7, 3
    for _ in range(rotation):
        points = [(shape_height - 1 - y, x) for x, y in points]
        shape_width, shape_height = shape_height, shape_width
    start_x, start_y = mx - shape_width // 2, my - shape_height // 2
    for dx, dy in points:
        box(d, (start_x + dx, start_y + dy, start_x + dx, start_y + dy), "water_dark")
    for dx, dy, width, height, color in RIPPLE_LAYOUTS[mask % len(RIPPLE_LAYOUTS)]:
        x, y = mx + dx, my + dy
        box(d, (x, y, x + width - 1, y + height - 1), color)

    # One fixed shoreline accent per exposed tile: a stone pair or three reeds.
    exposed = [side for side, connected in ((1, n), (2, e), (4, s), (8, w)) if not connected]
    if exposed:
        side = exposed[(mask // 2) % len(exposed)]
        if mask % 2 == 0:
            if side == 1: x, y = mx - 2, 2
            elif side == 2: x, y = 28, my - 2
            elif side == 4: x, y = mx - 2, 28
            else: x, y = 2, my - 2
            ellipse(d, (x, y + 1, x + 4, y + 3), "stone_dark")
            ellipse(d, (x + 1, y, x + 3, y + 2), "stone_light")
            box(d, (x + 1, y, x + 2, y), "stone_glow")
        else:
            if side == 1:
                bases = ((mx - 2, 4), (mx + 1, 4), (mx + 3, 4)); ends = tuple((x, y - 3) for x, y in bases)
            elif side == 2:
                bases = ((27, my - 2), (27, my + 1), (27, my + 3)); ends = tuple((x + 3, y) for x, y in bases)
            elif side == 4:
                bases = ((mx - 2, 27), (mx + 1, 27), (mx + 3, 27)); ends = tuple((x, y + 3) for x, y in bases)
            else:
                bases = ((4, my - 2), (4, my + 1), (4, my + 3)); ends = tuple((x - 3, y) for x, y in bases)
            for (x1, y1), (x2, y2) in zip(bases, ends):
                line(d, (x1, y1, x2, y2), "leaf_dark", 1)
            for x, y in bases:
                box(d, (x, y, x + 1, y + 1), "leaf")

        # One grass/sand/shallow-water pixel run per tile breaks the hard bright
        # sand band while keeping the transition small and readable.
        side = exposed[(mask + 1) % len(exposed)]
        offset = (mask % 3) - 1
        if side == 1:
            x = mx + 6 + offset
            box(d, (x, 0, x, 0), "grass_light")
            box(d, (x + 1, 1, x + 1, 1), "earth_light")
            box(d, (x + 1, 2, x + 1, 2), "earth")
            box(d, (x, 4, x, 4), "water_light")
        elif side == 2:
            y = my + 6 + offset
            box(d, (31, y, 31, y), "grass_light")
            box(d, (30, y + 1, 30, y + 1), "earth_light")
            box(d, (29, y + 1, 29, y + 1), "earth")
            box(d, (26, y, 26, y), "water_light")
        elif side == 4:
            x = mx - 6 - offset
            box(d, (x, 31, x, 31), "grass_light")
            box(d, (x - 1, 30, x - 1, 30), "earth_light")
            box(d, (x - 1, 29, x - 1, 29), "earth")
            box(d, (x, 26, x, 26), "water_light")
        else:
            y = my - 6 - offset
            box(d, (0, y, 0, y), "grass_light")
            box(d, (1, y - 1, 1, y - 1), "earth_light")
            box(d, (2, y - 1, 2, y - 1), "earth")
            box(d, (5, y, 5, y), "water_light")
    return im


def stone_path_tile(variant: int) -> Image.Image:
    im = grass_tile("meadow")
    d = ImageDraw.Draw(im)
    clusters = {
        1: [(3, 7, 10, 6), (16, 4, 12, 7), (10, 19, 13, 8)],
        2: [(2, 13, 12, 8), (17, 5, 10, 7), (17, 21, 12, 6)],
        3: [(4, 4, 11, 7), (18, 12, 11, 8), (5, 22, 12, 6)],
        4: [(4, 10, 9, 7), (16, 4, 13, 6), (15, 20, 11, 8)],
    }[variant]
    for x, y, width, height in clusters:
        ellipse(d, (x, y + 1, x + width, y + height), "stone_dark")
        ellipse(d, (x + 1, y, x + width - 1, y + height - 1), "stone")
        line(d, (x + 2, y + 1, x + width - 3, y + 1), "stone_light", 1)
        box(d, (x + 2, y + 2, x + 3, y + 2), "stone_glow")
    return im


def fence_rail_h(draw: ImageDraw.ImageDraw, x1: int, x2: int, y: int) -> None:
    """Five-pixel rail with a repeatable upper highlight and lower shade."""
    box(draw, (x1, y, x2, y + 4), "bark_dark")
    box(draw, (x1 + 1, y, x2 - 1, y + 1), "bark_light")
    box(draw, (x1 + 1, y + 2, x2 - 1, y + 3), "bark")


def fence_rail_v(draw: ImageDraw.ImageDraw, y1: int, y2: int, x: int) -> None:
    """Five-pixel rail with its highlight kept on the same northwest face."""
    box(draw, (x, y1, x + 4, y2), "bark_dark")
    box(draw, (x, y1 + 1, x + 1, y2 - 1), "bark_light")
    box(draw, (x + 2, y1 + 1, x + 3, y2 - 1), "bark")


def fence_center_post(draw: ImageDraw.ImageDraw, y1: int = 12, y2: int = 20) -> None:
    # Post width matches the five-pixel rail thickness; its cap and face
    # highlight occupy the same pixels in every junction mask.
    box(draw, (14, y1, 18, y2), "bark_dark")
    box(draw, (15, y1 + 1, 17, y2 - 1), "bark")
    box(draw, (14, y1, 18, y1 + 1), "bark_light")
    box(draw, (15, y1 - 1, 17, y1 - 1), "cream")
    box(draw, (15, y1 + 3, 16, y1 + 4), "bark_light")


def fence_tile(mask: int) -> Image.Image:
    im = new_tile()
    d = ImageDraw.Draw(im)
    if mask == 0:
        box(d, (14, 15, 18, 30), "bark_dark")
        box(d, (15, 16, 17, 29), "bark")
        box(d, (14, 15, 18, 16), "bark_light")
        box(d, (15, 14, 17, 14), "cream")
        return im
    if mask & 1:
        fence_rail_v(d, 0, 16, 10)
        fence_rail_v(d, 0, 16, 18)
    if mask & 4:
        fence_rail_v(d, 15, 31, 10)
        fence_rail_v(d, 15, 31, 18)
    if mask & 8:
        fence_rail_h(d, 0, 16, 10)
        fence_rail_h(d, 0, 16, 20)
    if mask & 2:
        fence_rail_h(d, 15, 31, 10)
        fence_rail_h(d, 15, 31, 20)
    fence_center_post(d)
    return im


def gate_tile(opened: bool) -> Image.Image:
    im = fence_tile(10)
    d = ImageDraw.Draw(im)
    if opened:
        # The leaf swings north along the east hinge, leaving the centre lane open.
        im = new_tile()
        d = ImageDraw.Draw(im)
        fence_rail_v(d, 8, 29, 25)
        for y in (9, 16, 23):
            fence_rail_h(d, 21, 29, y)
        box(d, (26, 7, 28, 7), "cream")
        box(d, (23, 16, 24, 17), "sun")
    else:
        # A closed leaf spans both rails, with aligned stiles and a latch.
        fence_rail_v(d, 12, 22, 7)
        fence_rail_v(d, 12, 22, 22)
        box(d, (23, 16, 24, 17), "sun")
    return im


def tree_tile(variant: int) -> Image.Image:
    im = new_tile()
    d = ImageDraw.Draw(im)
    ellipse(d, (3, 25, 29, 31), "leaf_dark")
    box(d, (13, 19, 19, 30), "bark_dark")
    box(d, (14, 18, 18, 28), "bark")
    box(d, (14, 19, 15, 25), "bark_light")
    # Layered crown silhouette with distinct scallops and a lit upper-left rim.
    if variant == 1:
        parts = [((3, 9, 18, 23), "leaf_dark"), ((11, 5, 27, 23), "leaf_dark"), ((6, 4, 22, 19), "leaf"),
                 ((4, 8, 17, 19), "leaf_bright"), ((12, 7, 22, 15), "leaf_pale"),
                 ((19, 11, 27, 21), "leaf")]
    else:
        parts = [((3, 8, 19, 22), "leaf_dark"), ((13, 4, 28, 22), "leaf_dark"), ((5, 3, 22, 18), "leaf_bright"),
                 ((3, 10, 14, 19), "leaf"), ((10, 5, 19, 13), "leaf_pale"), ((19, 10, 27, 18), "leaf")]
    for coords, color in parts:
        ellipse(d, coords, color)
    for x, y in ((8, 10), (15, 7), (21, 14), (11, 17)):
        box(d, (x, y, x + 2, y + 1), "leaf_pale")
    if variant == 1:
        for x, y in ((8, 16), (22, 9), (17, 19)):
            ellipse(d, (x, y, x + 3, y + 3), "sun")
            box(d, (x + 1, y + 1, x + 1, y + 1), "coral")
    else:
        for x, y in ((8, 14), (22, 11)):
            box(d, (x, y, x + 1, y + 2), "cream")
            box(d, (x + 1, y + 1, x + 2, y + 2), "sun")
    return im


def greenhouse_parts() -> list[tuple[str, Image.Image]]:
    im = Image.new("RGBA", (64, 64), TRANSPARENT)
    d = ImageDraw.Draw(im)
    ellipse(d, (3, 54, 61, 62), "grass_dark")
    # A glasshouse roofline, brick sill and wood framing are authored together,
    # then sliced on exact tile boundaries to keep seams aligned.
    polygon(d, [(3, 17), (9, 10), (31, 2), (54, 10), (61, 17), (58, 21), (7, 21)], "ink")
    polygon(d, [(6, 16), (11, 12), (31, 5), (52, 12), (58, 16), (56, 19), (8, 19)], "bark")
    line(d, (12, 13, 31, 6), "bark_light", 2)
    line(d, (31, 6, 51, 13), "bark_light", 2)
    line(d, (12, 12, 27, 7), "stone_glow", 1)
    line(d, (35, 7, 49, 12), "stone_glow", 1)
    box(d, (6, 18, 57, 54), "ink")
    box(d, (9, 20, 54, 51), "water_dark")
    # Four glass panes, with top-left reflections and substantial warm framing.
    for x1, x2 in ((11, 29), (34, 52)):
        for y1, y2 in ((22, 35), (38, 49)):
            box(d, (x1, y1, x2, y2), "water_light")
            box(d, (x1 + 1, y1 + 1, x1 + 4, y1 + 5), "sky_light")
            box(d, (x1 + 5, y2 - 2, x2 - 2, y2 - 1), "water")
    box(d, (30, 19, 33, 52), "bark_dark")
    box(d, (31, 20, 32, 50), "bark_light")
    box(d, (7, 35, 56, 38), "bark_dark")
    box(d, (8, 35, 55, 36), "bark_light")
    # Door occupies the right half of the lower-right bay.
    box(d, (38, 37, 49, 53), "bark_dark")
    box(d, (40, 38, 48, 51), "bark")
    box(d, (41, 39, 46, 43), "bark_light")
    box(d, (46, 45, 47, 46), "sun")
    # Pale stone sill and its shaded bottom course.
    box(d, (5, 52, 59, 57), "stone_dark")
    box(d, (6, 52, 58, 55), "stone_light")
    for x in (9, 20, 31, 42, 53):
        box(d, (x, 53, x + 4, 55), "stone_glow")
    # Doorstep and potted sprout make the assembled structure feel lived-in.
    box(d, (38, 55, 50, 57), "stone_dark")
    box(d, (39, 54, 49, 55), "stone_glow")
    return [(name, im.crop((x, y, x + 32, y + 32))) for name, x, y in
            (("greenhouse_nw", 0, 0), ("greenhouse_ne", 32, 0),
             ("greenhouse_sw", 0, 32), ("greenhouse_se", 32, 32))]


FLOWERS = {
    "daisy": {"variants": {"ivory": ("cream", "sun"), "rose": ("coral_light", "sun")}, "shape": "daisy"},
    "tulip": {"variants": {"coral": ("coral", "coral_light"), "gold": ("sun", "cream")}, "shape": "tulip"},
    "bluebell": {"variants": {"lavender": ("lavender", "lavender_light"), "sky": ("sky", "sky_light")}, "shape": "bell"},
    "cosmos": {"variants": {"pink": ("coral_light", "cream"), "violet": ("lavender", "sun")}, "shape": "cosmos"},
}


def flower_tile(species: str, bloom: str, center: str, stage: int) -> Image.Image:
    im = new_tile()
    d = ImageDraw.Draw(im)
    ellipse(d, (10, 27, 22, 30), "leaf_dark")
    seedling_specs = {"daisy": (7, 3), "tulip": (9, 5), "bluebell": (8, 4), "cosmos": (10, 6)}
    stem_height = seedling_specs[species][0] if stage == 1 else {2: 13, 3: 16}[stage]
    base_y = 26
    head_y = base_y - stem_height
    line(d, (16, base_y, 16, head_y + 3), "leaf_dark", 2)
    line(d, (16, base_y - 2, 16, head_y + 4), "leaf_bright", 1)
    if stage >= 1:
        if stage == 1:
            leaf_pair(d, 20, seedling_specs[species][1])
        else:
            polygon(d, [(15, 23), (10, 20), (9, 17), (14, 19), (16, 22)], "leaf")
            polygon(d, [(16, 22), (20, 18), (24, 17), (21, 21), (17, 24)], "leaf_bright")
            box(d, (11, 20, 13, 20), "leaf_pale")
    if stage == 1:
        ellipse(d, (14, head_y + 2, 17, head_y + 5), "leaf_bright")
        return im
    if stage == 2:
        if species == "bluebell":
            for dx in (-4, 0, 4):
                ellipse(d, (15 + dx, head_y + 2, 18 + dx, head_y + 6), bloom)
        elif species == "tulip":
            polygon(d, [(13, head_y + 6), (13, head_y + 2), (15, head_y), (17, head_y + 2),
                        (19, head_y), (20, head_y + 6), (17, head_y + 8)], bloom)
        else:
            ellipse(d, (12, head_y + 1, 20, head_y + 8), bloom)
            box(d, (15, head_y + 3, 17, head_y + 5), center)
        return im
    shape = FLOWERS[species]["shape"]
    if shape == "daisy":
        for x, y, ww, hh in ((16, head_y, 3, 4), (12, head_y + 1, 4, 3), (20, head_y + 1, 4, 3),
                             (13, head_y + 6, 4, 3), (19, head_y + 6, 4, 3), (16, head_y + 8, 3, 3)):
            ellipse(d, (x, y, x + ww - 1, y + hh - 1), bloom)
        ellipse(d, (15, head_y + 3, 19, head_y + 7), center)
        box(d, (16, head_y + 3, 17, head_y + 4), "cream")
    elif shape == "tulip":
        polygon(d, [(11, head_y + 8), (12, head_y + 3), (14, head_y), (16, head_y + 3),
                    (18, head_y), (20, head_y + 3), (22, head_y + 8), (18, head_y + 10), (14, head_y + 10)], bloom)
        line(d, (15, head_y + 3, 16, head_y + 8), center, 1)
        box(d, (13, head_y + 3, 14, head_y + 4), "cream")
    elif shape == "bell":
        for x, y in ((11, head_y + 3), (16, head_y + 1), (21, head_y + 4)):
            box(d, (x + 1, y - 2, x + 2, y), "leaf_bright")
            polygon(d, [(x, y), (x + 4, y), (x + 5, y + 4), (x + 3, y + 7), (x + 1, y + 6)], bloom)
            box(d, (x + 1, y + 5, x + 3, y + 6), center)
        box(d, (12, head_y + 4, 12, head_y + 4), "cream")
    else:  # cosmos, evenly tapered pointed petals
        for x, y, points in ((15, head_y, [(2, 0), (4, 2), (3, 5), (1, 5), (0, 2)]),
                             (11, head_y + 3, [(0, 2), (2, 0), (5, 1), (4, 3), (1, 4)]),
                             (19, head_y + 3, [(0, 1), (3, 0), (5, 2), (4, 4), (1, 3)]),
                             (14, head_y + 6, [(1, 0), (3, 0), (4, 3), (2, 5), (0, 3)])):
            polygon(d, [(x + a, y + b) for a, b in points], bloom)
        ellipse(d, (15, head_y + 3, 18, head_y + 6), center)
    return im


def leaf_pair(d: ImageDraw.ImageDraw, y: int, spread: int) -> None:
    polygon(d, [(15, y + 3), (15 - spread, y), (14 - spread, y + 3), (16, y + 5)], "leaf")
    polygon(d, [(17, y + 3), (17 + spread, y), (18 + spread, y + 3), (16, y + 5)], "leaf_bright")
    box(d, (15 - spread + 1, y + 1, 15 - spread + 2, y + 1), "leaf_pale")


def crop_tile(crop: str, stage: int) -> Image.Image:
    im = new_tile()
    d = ImageDraw.Draw(im)
    ellipse(d, (8, 26, 24, 30), "earth_dark")
    box(d, (11, 27, 20, 28), "earth")
    if crop == "carrot":
        leaf_pair(d, 19, 5 if stage >= 2 else 3)
        if stage >= 2:
            leaf_pair(d, 14, 7)
        if stage >= 3:
            leaf_pair(d, 9, 5)
        if stage == 4:
            polygon(d, [(13, 22), (19, 22), (18, 27), (16, 30), (14, 27)], "carrot")
            line(d, (14, 23, 18, 23), "sun", 1)
            box(d, (16, 24, 16, 25), "earth_gold")
    elif crop == "tomato":
        line(d, (16, 27, 16, 17 if stage >= 2 else 22), "leaf_dark", 2)
        if stage >= 2:
            leaf_pair(d, 19, 7)
            leaf_pair(d, 14, 6)
        else:
            leaf_pair(d, 21, 3)
        if stage >= 3:
            polygon(d, [(16, 18), (11, 15), (9, 17), (13, 20)], "leaf")
            polygon(d, [(16, 17), (21, 14), (23, 16), (19, 19)], "leaf_bright")
            for x, y in ((12, 20), (19, 20)):
                ellipse(d, (x, y, x + 4, y + 4), "leaf_pale" if stage == 3 else "tomato")
                if stage == 4:
                    box(d, (x + 1, y + 1, x + 2, y + 1), "tomato_light")
            if stage == 4:
                ellipse(d, (14, 16, 19, 20), "tomato")
                box(d, (15, 17, 16, 17), "tomato_light")
    elif crop == "cabbage":
        if stage == 1:
            ellipse(d, (12, 22, 17, 27), "leaf_dark")
            ellipse(d, (15, 20, 20, 26), "leaf_bright")
            box(d, (12, 20, 13, 20), "grass_light")
        elif stage == 2:
            ellipse(d, (8, 22, 15, 27), "leaf_dark")
            ellipse(d, (13, 19, 21, 27), "leaf_bright")
            ellipse(d, (18, 22, 24, 27), "leaf")
            ellipse(d, (12, 17, 18, 22), "leaf_pale")
        elif stage == 3:
            ellipse(d, (7, 21, 15, 27), "leaf_dark")
            ellipse(d, (10, 18, 17, 27), "leaf")
            ellipse(d, (15, 17, 23, 27), "leaf_bright")
            ellipse(d, (19, 21, 25, 27), "leaf_dark")
            ellipse(d, (11, 16, 21, 25), "leaf_pale")
            ellipse(d, (13, 17, 19, 23), "leaf_bright")
        else:
            ellipse(d, (6, 21, 15, 27), "leaf_dark")
            ellipse(d, (9, 18, 17, 28), "leaf")
            ellipse(d, (16, 18, 24, 27), "leaf_dark")
            ellipse(d, (10, 14, 23, 27), "leaf_bright")
            ellipse(d, (12, 14, 20, 22), "leaf_pale")
            line(d, (16, 16, 16, 23), "grass_light", 1)
            line(d, (16, 19, 13, 17), "grass_light", 1)
    else:  # sunflower
        stem_top = {1: 22, 2: 16, 3: 12, 4: 10}[stage]
        line(d, (16, 27, 16, stem_top + 4), "leaf_dark", 2)
        line(d, (16, 26, 16, stem_top + 5), "leaf_bright", 1)
        leaf_pair(d, max(19, stem_top + 6), 4 if stage < 3 else 6)
        if stage >= 3:
            leaf_pair(d, stem_top + 10, 5)
        if stage == 1:
            ellipse(d, (14, stem_top, 18, stem_top + 4), "leaf_bright")
            box(d, (14, stem_top, 14, stem_top), "leaf_pale")
        elif stage == 2:
            ellipse(d, (13, stem_top, 19, stem_top + 6), "leaf_dark")
            ellipse(d, (14, stem_top + 1, 18, stem_top + 4), "leaf_pale")
        else:
            for x, y in ((14, stem_top), (12, stem_top + 2), (18, stem_top + 2), (14, stem_top + 5)):
                ellipse(d, (x, y, x + 4, y + 3), "sun")
            ellipse(d, (14, stem_top + 1, 18, stem_top + 5), "earth_dark")
            for x, y in ((15, stem_top + 2), (17, stem_top + 3), (15, stem_top + 4)):
                box(d, (x, y, x, y), "earth_gold")
            if stage == 4:
                box(d, (15, stem_top + 2, 15, stem_top + 2), "cream")
    return im


def harvest_tile(item: str) -> Image.Image:
    im = new_tile()
    d = ImageDraw.Draw(im)
    ellipse(d, (6, 25, 25, 30), "leaf_dark")
    if item == "carrot":
        polygon(d, [(8, 14), (22, 9), (21, 15), (16, 24), (13, 26), (12, 21)], "carrot")
        line(d, (10, 15, 19, 12), "sun", 2)
        line(d, (15, 19, 17, 18), "earth_gold", 1)
        polygon(d, [(9, 14), (5, 9), (12, 11), (14, 7), (16, 12)], "leaf")
        polygon(d, [(10, 13), (17, 8), (17, 12), (12, 15)], "leaf_bright")
    elif item == "tomato":
        ellipse(d, (8, 9, 24, 25), "tomato")
        polygon(d, [(15, 8), (17, 4), (19, 9), (24, 8), (21, 12), (16, 11), (11, 13), (13, 9)], "leaf")
        ellipse(d, (11, 11, 14, 14), "tomato_light")
        box(d, (11, 11, 11, 11), "cream")
        box(d, (18, 20, 20, 21), "coral")
    elif item == "cabbage":
        ellipse(d, (6, 12, 26, 28), "leaf_dark")
        ellipse(d, (8, 9, 23, 26), "leaf_bright")
        ellipse(d, (11, 10, 21, 23), "leaf_pale")
        line(d, (16, 12, 16, 22), "grass_light", 1)
        line(d, (16, 18, 12, 16), "grass_light", 1)
        line(d, (16, 19, 20, 16), "leaf", 1)
    else:
        ellipse(d, (8, 8, 24, 24), "sun")
        ellipse(d, (11, 11, 21, 21), "earth_dark")
        for x, y in ((13, 13), (17, 13), (15, 16), (19, 17), (13, 19), (17, 20)):
            box(d, (x, y, x + 1, y + 1), "earth_gold")
        polygon(d, [(11, 25), (8, 21), (12, 22), (15, 26)], "leaf")
        polygon(d, [(20, 25), (23, 21), (20, 22), (17, 26)], "leaf_bright")
    return im


def lily_pad_tile() -> Image.Image:
    im = new_tile()
    d = ImageDraw.Draw(im)
    ellipse(d, (5, 19, 27, 26), "water_dark")
    outline = [(11, 9), (15, 15), (16, 8), (22, 10), (26, 14), (27, 18),
               (23, 22), (16, 24), (10, 22), (7, 18), (6, 14), (9, 11)]
    polygon(d, outline, "leaf_dark")
    face = [(12, 10), (15, 15), (16, 9), (21, 11), (25, 14), (25, 17),
            (22, 21), (16, 22), (11, 20), (8, 17), (8, 14)]
    polygon(d, face, "leaf")
    polygon(d, [(10, 13), (12, 11), (15, 14), (14, 16), (11, 16)], "leaf_pale")
    polygon(d, [(19, 17), (23, 15), (24, 18), (21, 21), (18, 20)], "leaf_dark")
    line(d, (15, 15, 11, 14), "leaf_pale", 1)
    line(d, (15, 16, 13, 19), "leaf_bright", 1)
    return im


def pond_rock_tile() -> Image.Image:
    im = new_tile()
    d = ImageDraw.Draw(im)
    ellipse(d, (6, 22, 27, 28), "water_dark")
    polygon(d, [(7, 20), (8, 15), (12, 10), (18, 7), (23, 9), (27, 15),
                (26, 20), (22, 24), (14, 25), (9, 23)], "stone_dark")
    polygon(d, [(9, 19), (10, 15), (13, 11), (18, 9), (22, 11), (25, 15),
                (24, 19), (21, 22), (14, 23), (10, 21)], "stone")
    polygon(d, [(10, 15), (13, 11), (18, 9), (19, 13), (15, 16)], "stone_light")
    box(d, (12, 12, 14, 12), "stone_glow")
    polygon(d, [(20, 16), (24, 15), (24, 19), (21, 22), (18, 21)], "stone_dark")
    return im


def prop_tile(kind: str) -> Image.Image:
    im = new_tile()
    d = ImageDraw.Draw(im)
    if kind == "terracotta_pot":
        ellipse(d, (7, 25, 25, 30), "leaf_dark")
        box(d, (9, 11, 22, 14), "bark_dark")
        box(d, (10, 12, 21, 13), "coral_light")
        polygon(d, [(10, 14), (21, 14), (19, 25), (12, 25)], "coral")
        line(d, (12, 16, 18, 16), "coral_light", 1)
        box(d, (12, 22, 19, 24), "tomato")
        box(d, (8, 10, 23, 11), "coral_light")
        for x, y in ((12, 8), (16, 6), (20, 9)):
            box(d, (x, y, x + 1, y + 3), "leaf")
        box(d, (15, 7, 17, 8), "leaf_pale")
    elif kind == "bench":
        ellipse(d, (3, 25, 29, 30), "leaf_dark")
        box(d, (4, 12, 27, 21), "bark_dark")
        for y, col in ((13, "bark_light"), (16, "bark"), (19, "bark_light")):
            box(d, (5, y, 26, y + 1), col)
        box(d, (6, 21, 9, 27), "bark_dark"); box(d, (7, 22, 8, 26), "bark_light")
        box(d, (22, 21, 25, 27), "bark_dark"); box(d, (23, 22, 24, 26), "bark")
        box(d, (5, 7, 8, 13), "bark_dark"); box(d, (6, 8, 7, 12), "bark")
        box(d, (23, 7, 26, 13), "bark_dark"); box(d, (24, 8, 25, 12), "bark")
        box(d, (4, 7, 27, 10), "bark_dark"); box(d, (5, 7, 26, 8), "bark_light")
        box(d, (5, 7, 5, 7), "cream")
    elif kind == "watering_can":
        ellipse(d, (5, 24, 27, 30), "leaf_dark")
        box(d, (10, 13, 23, 23), "water_dark")
        box(d, (11, 12, 22, 21), "sky")
        box(d, (12, 13, 19, 15), "sky_light")
        box(d, (13, 17, 19, 20), "sky")
        polygon(d, [(21, 15), (29, 11), (30, 13), (23, 19)], "stone_dark")
        polygon(d, [(22, 15), (28, 12), (28, 13), (23, 17)], "stone_light")
        box(d, (27, 10, 31, 12), "stone_dark")
        box(d, (28, 10, 30, 10), "stone_glow")
        line(d, (11, 13, 13, 8), "water_dark", 2); line(d, (13, 8, 21, 8), "water_dark", 2)
        line(d, (13, 9, 20, 9), "stone_light", 1)
    elif kind == "seed_bag":
        ellipse(d, (6, 26, 26, 30), "leaf_dark")
        polygon(d, [(8, 9), (24, 9), (26, 25), (7, 25)], "bark_dark")
        polygon(d, [(10, 10), (22, 10), (23, 23), (9, 23)], "cream")
        box(d, (10, 10, 22, 12), "earth_gold")
        polygon(d, [(16, 20), (16, 15), (13, 13), (12, 16), (15, 18), (17, 15), (20, 14), (19, 17)], "leaf")
        line(d, (16, 20, 16, 13), "leaf_dark", 1)
        box(d, (7, 8, 25, 10), "bark")
    elif kind == "signpost":
        ellipse(d, (7, 26, 25, 30), "leaf_dark")
        box(d, (14, 15, 18, 29), "bark_dark")
        box(d, (15, 16, 17, 27), "bark_light")
        polygon(d, [(4, 5), (26, 5), (29, 8), (26, 16), (4, 16), (2, 12)], "bark_dark")
        polygon(d, [(5, 6), (25, 6), (27, 8), (25, 14), (5, 14), (4, 11)], "bark")
        box(d, (7, 8, 21, 9), "bark_light")
        pxtext(d, 8, 9, "GROW", "cream", 1)
    elif kind == "crate":
        ellipse(d, (5, 25, 27, 30), "leaf_dark")
        box(d, (6, 10, 26, 25), "bark_dark")
        box(d, (8, 12, 24, 23), "bark")
        for y in (13, 17, 21):
            box(d, (7, y, 25, y + 1), "bark_light")
        box(d, (6, 10, 9, 13), "cream"); box(d, (23, 10, 26, 13), "cream")
        box(d, (14, 15, 18, 19), "bark_dark")
    elif kind == "basket":
        ellipse(d, (5, 25, 27, 30), "leaf_dark")
        box(d, (7, 14, 25, 26), "bark_dark")
        polygon(d, [(9, 16), (23, 16), (21, 24), (11, 24)], "bark_light")
        line(d, (10, 18, 22, 18), "bark_dark", 2)
        line(d, (11, 21, 21, 21), "bark_dark", 1)
        line(d, (9, 14, 11, 9), "bark_dark", 2); line(d, (11, 9, 21, 9), "bark_dark", 2)
        line(d, (21, 9, 24, 14), "bark_dark", 2)
        for x in (12, 16, 20): box(d, (x, 10, x + 2, 14), "leaf")
        box(d, (8, 15, 8, 15), "stone_glow")
    else:  # bird bath
        ellipse(d, (5, 26, 27, 30), "leaf_dark")
        box(d, (14, 14, 18, 27), "stone_dark")
        box(d, (15, 15, 17, 25), "stone_light")
        ellipse(d, (6, 10, 26, 18), "stone_dark")
        ellipse(d, (8, 9, 24, 16), "stone_light")
        ellipse(d, (10, 10, 22, 14), "water")
        box(d, (12, 10, 16, 11), "water_light")
    return im


def critter_tile(kind: str) -> Image.Image:
    im = new_tile()
    d = ImageDraw.Draw(im)
    if kind == "bee":
        ellipse(d, (5, 19, 26, 27), "leaf_dark")
        ellipse(d, (9, 14, 22, 23), "earth_dark")
        ellipse(d, (10, 13, 21, 21), "sun")
        box(d, (14, 14, 15, 21), "earth_dark"); box(d, (18, 14, 19, 21), "earth_dark")
        ellipse(d, (7, 9, 15, 15), "sky_light"); ellipse(d, (16, 8, 23, 14), "cream")
        box(d, (20, 15, 21, 16), "cream")
        line(d, (11, 13, 9, 10), "bark_dark", 1); line(d, (17, 13, 19, 9), "bark_dark", 1)
        line(d, (10, 21, 8, 24), "earth_dark", 1); line(d, (18, 21, 20, 24), "earth_dark", 1)
    elif kind == "butterfly":
        ellipse(d, (5, 10, 15, 22), "earth_dark")
        ellipse(d, (17, 9, 27, 21), "earth_dark")
        ellipse(d, (7, 11, 14, 19), "coral")
        ellipse(d, (18, 10, 25, 18), "lavender")
        ellipse(d, (10, 14, 13, 17), "sun")
        ellipse(d, (20, 12, 23, 15), "cream")
        box(d, (15, 11, 17, 24), "earth_dark")
        line(d, (16, 12, 12, 7), "earth_dark", 1); line(d, (16, 12, 20, 7), "earth_dark", 1)
        line(d, (7, 22, 10, 25), "earth_dark", 1); line(d, (24, 21, 21, 25), "earth_dark", 1)
    else:  # snail
        ellipse(d, (5, 21, 27, 27), "leaf_dark")
        polygon(d, [(7, 20), (10, 17), (25, 17), (28, 21), (26, 25), (9, 25)], "earth_dark")
        polygon(d, [(9, 20), (12, 18), (24, 18), (26, 21), (24, 23), (10, 23)], "moss")
        ellipse(d, (11, 8, 23, 21), "earth_dark")
        ellipse(d, (13, 9, 21, 19), "earth_gold")
        ellipse(d, (15, 11, 20, 16), "earth")
        ellipse(d, (16, 12, 18, 14), "bark_light")
        box(d, (25, 16, 26, 19), "earth_dark")
        box(d, (24, 13, 25, 14), "earth_dark"); box(d, (27, 13, 28, 14), "earth_dark")
        box(d, (13, 10, 14, 10), "stone_glow")
    return im


def build_sprites() -> list[dict]:
    records: list[dict] = []
    for kind in GRASS_VARIANTS:
        records.append(save_tile(f"tiles/grass_{kind}.png", grass_tile(kind), "ground"))
    for kind, category in (("tilled", "ground"), ("wet", "ground"), ("seeded", "ground"), ("raised", "ground")):
        name = "planter_bed" if kind == "raised" else f"soil_{kind}"
        records.append(save_tile(f"tiles/{name}.png", soil_tile(kind), category))
    for variant in range(1, 5):
        records.append(save_tile(f"tiles/stone_path_{variant:02}.png", stone_path_tile(variant), "ground"))
    for mask in range(16):
        records.append(save_tile(f"tiles/path_auto_{mask:02}.png", path_tile(mask), "autotile"))
        records.append(save_tile(f"tiles/water_auto_{mask:02}.png", water_tile(mask), "autotile"))
    for mask in range(16):
        records.append(save_tile(f"tiles/fence_auto_{mask:02}.png", fence_tile(mask), "fence", collision="thin post/rail"))
    records.append(save_tile("tiles/fence_gate_closed.png", gate_tile(False), "fence", collision="closed gate"))
    records.append(save_tile("tiles/fence_gate_open.png", gate_tile(True), "fence", collision="posts only"))
    for variant in (1, 2):
        records.append(save_tile(f"trees/tree_{'apple' if variant == 1 else 'pear'}_{variant:02}.png",
                                 tree_tile(variant), "prop", pivot="bottom-center", collision="trunk: 8x8 at bottom-center"))
    for name, image in greenhouse_parts():
        records.append(save_tile(f"structures/{name}.png", image, "structure", pivot="top-left", collision="building footprint"))
    for species, data in FLOWERS.items():
        for variant, colors in data["variants"].items():
            for stage in (1, 2, 3):
                records.append(save_tile(f"flowers/flower_{species}_{variant}_stage_{stage:02}.png",
                                         flower_tile(species, colors[0], colors[1], stage), "flower", pivot="bottom-center"))
    for crop in ("carrot", "tomato", "cabbage", "sunflower"):
        for stage in (1, 2, 3, 4):
            records.append(save_tile(f"crops/crop_{crop}_stage_{stage:02}.png", crop_tile(crop, stage), "crop", pivot="bottom-center"))
        records.append(save_tile(f"crops/harvest_{crop}.png", harvest_tile(crop), "harvest", pivot="center"))
    for prop in ("terracotta_pot", "bench", "watering_can", "seed_bag", "signpost", "crate", "basket", "birdbath"):
        collision = "solid footprint: center-bottom 12x6" if prop in ("bench", "crate", "birdbath") else "none"
        records.append(save_tile(f"props/prop_{prop}.png", prop_tile(prop), "prop", pivot="bottom-center", collision=collision))
    records.append(save_tile("props/prop_lily_pad.png", lily_pad_tile(), "prop", pivot="center", collision="none"))
    records.append(save_tile("props/prop_pond_rock.png", pond_rock_tile(), "prop", pivot="bottom-center", collision="none"))
    for critter in ("bee", "butterfly", "snail"):
        records.append(save_tile(f"critters/critter_{critter}.png", critter_tile(critter), "critter", pivot="bottom-center"))
    return records


def write_palette() -> None:
    palfile = ASSETS / "palette.gpl"
    lines = ["GIMP Palette", "Name: Cozy Garden 32x32", "Columns: 6", "# 36 opaque inks plus transparent"]
    for name, value in P.items():
        r, g, b = (int(value[i:i + 2], 16) for i in (1, 3, 5))
        lines.append(f"{r:3d} {g:3d} {b:3d}\t{name}")
    lines.append("  0   0   0\ttransparent (RGBA 0,0,0,0)")
    palfile.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (ASSETS / "palette.json").write_text(json.dumps({"name": "Cozy Garden 32x32", "transparent": "#00000000",
                                                       "colors": P}, indent=2) + "\n", encoding="utf-8")
    cols, cell_w, cell_h = 4, 184, 58
    rows = math.ceil((len(P) + 1) / cols)
    im = Image.new("RGBA", (cols * cell_w, rows * cell_h + 36), C["cream"])
    d = ImageDraw.Draw(im)
    pxtext(d, 10, 8, "COZY GARDEN PALETTE 36 + TRANSPARENT", "ink", 2)
    entries: list[tuple[str, str | None]] = list(P.items()) + [("transparent", None)]
    for idx, (name, value) in enumerate(entries):
        x = (idx % cols) * cell_w + 8
        y = (idx // cols) * cell_h + 34
        if value is None:
            for yy in range(28):
                for xx in range(36):
                    color = "stone_light" if ((xx // 7 + yy // 7) % 2) else "cream"
                    box(d, (x + xx, y + yy, x + xx, y + yy), color)
            d.rectangle((x, y, x + 35, y + 27), outline=C["ink"], width=1)
            pxtext(d, x + 44, y + 2, "TRANSPARENT", "ink", 2)
            pxtext(d, x + 44, y + 16, "00000000", "ink_soft", 2)
        else:
            box(d, (x, y, x + 35, y + 27), name)
            pxtext(d, x + 44, y + 1, name.upper(), "ink", 2)
            pxtext(d, x + 44, y + 15, value[1:], "ink_soft", 2)
    im.save(ASSETS / "palette.png", format="PNG")


def grass_repeat_variant(x: int, y: int) -> int:
    """Six-way deterministic weave with no identical horizontal or vertical neighbours."""
    return (x + 2 * y + y // 2) % len(GRASS_VARIANTS)


def grass_repeat_test_image() -> Image.Image:
    canvas = Image.new("RGBA", (8 * SIZE, 8 * SIZE), C["grass"])
    tiles = {kind: Image.open(ASSETS / f"tiles/grass_{kind}.png").convert("RGBA")
             for kind in GRASS_VARIANTS}
    for y in range(8):
        for x in range(8):
            kind = GRASS_VARIANTS[grass_repeat_variant(x, y)]
            canvas.alpha_composite(tiles[kind], (x * SIZE, y * SIZE))
    return canvas.resize((canvas.width * SCALE, canvas.height * SCALE), Image.Resampling.NEAREST)


def write_tile_repeat_test() -> None:
    grass_repeat_test_image().save(ASSETS / "tile-repeat-test.png", format="PNG", optimize=False)


def write_atlas(records: list[dict]) -> None:
    columns = 10
    rows = math.ceil(len(records) / columns)
    atlas = Image.new("RGBA", (columns * SIZE, rows * SIZE), TRANSPARENT)
    for idx, record in enumerate(records):
        sprite = Image.open(ASSETS / record["path"]).convert("RGBA")
        x, y = (idx % columns) * SIZE, (idx // columns) * SIZE
        atlas.alpha_composite(sprite, (x, y))
        record["atlas"] = {"x": x, "y": y, "w": SIZE, "h": SIZE, "index": idx}
    atlas.save(ASSETS / "tileset-sheet.png", format="PNG", optimize=False)
    manifest = {
        "name": "Cozy Garden v3 — 32×32 tiles & sprites",
        "tile_size": [32, 32], "columns": columns, "rows": rows,
        "sheet": "tileset-sheet.png", "filter": "nearest", "pixels_per_unit": 32,
        "mask_bits": {"N": 1, "E": 2, "S": 4, "W": 8},
        "art_direction": SHADING_RULE,
        "grass_arrangements": {f"tiles/grass_{kind}.png": {"density": density}
                               for kind, density in GRASS_DENSITY.items()},
        "water_detail_rule": {
            "ripple_marks_per_tile": 3,
            "placement": "fixed mask-indexed offsets around the water-body centre; see RIPPLE_LAYOUTS in source/generate_pack.py",
            "shoreline": "muted earth banks, shallow mid-tone patches, grass-to-sand-to-water transitions, and one fixed stone or reed accent on an exposed side",
            "reflection_mapping": {f"{mask:02}": {"shape": REFLECTION_NAMES[shape], "rotation_degrees": rotation * 90}
                                   for mask, (shape, rotation) in enumerate(REFLECTION_MASK_MAP)},
        },
        "terrain_autotiles": {"path": "tiles/path_auto_NN.png", "water": "tiles/water_auto_NN.png",
                              "fence": "tiles/fence_auto_NN.png", "NN": "two-digit cardinal bitmask 00-15"},
        "assets": records,
    }
    (ASSETS / "tileset-sheet-map.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def draw_scene(records: list[dict]) -> None:
    # A deterministic, quiet lawn with planted patches and a compact route to
    # both the greenhouse and the entrance. Every layer remains in the sidecar.
    ground = [["grass_meadow" for _ in range(10)] for _ in range(10)]
    for x, y in ((1, 0), (3, 0), (0, 2), (2, 2), (3, 2)):
        ground[y][x] = "grass_clover"
    for x, y in ((1, 4), (3, 4)):
        ground[y][x] = "grass_blossom"
    for x, y in ((6, 6), (9, 6), (6, 8), (8, 8), (9, 8)):
        ground[y][x] = "grass_moss"
    path_cells: set[tuple[int, int]] = {(5, y) for y in range(3, 10)} | {(x, 3) for x in range(6, 9)}
    water_cells: set[tuple[int, int]] = {
        (7, 6), (8, 6), (6, 7), (7, 7), (8, 7), (7, 8),
    }
    canvas = Image.new("RGBA", (10 * SIZE, 10 * SIZE), C["grass"])
    for y in range(10):
        for x in range(10):
            tile = Image.open(ASSETS / f"tiles/{ground[y][x]}.png").convert("RGBA")
            canvas.alpha_composite(tile, (x * SIZE, y * SIZE))
    for x, y in water_cells:
        mask = 0
        for bit, (dx, dy) in ((1, (0, -1)), (2, (1, 0)), (4, (0, 1)), (8, (-1, 0))):
            if (x + dx, y + dy) in water_cells:
                mask |= bit
        tile = Image.open(ASSETS / f"tiles/water_auto_{mask:02}.png").convert("RGBA")
        canvas.alpha_composite(tile, (x * SIZE, y * SIZE))
    for x, y in path_cells:
        mask = 0
        for bit, (dx, dy) in ((1, (0, -1)), (2, (1, 0)), (4, (0, 1)), (8, (-1, 0))):
            if (x + dx, y + dy) in path_cells:
                mask |= bit
        tile = Image.open(ASSETS / f"tiles/path_auto_{mask:02}.png").convert("RGBA")
        canvas.alpha_composite(tile, (x * SIZE, y * SIZE))
    # Raised bed soil uses a pair of 2x2 frames built from real 32px ground and fence layers.
    overlays: list[dict] = []
    for bx in (1, 3):
        by = 5
        for dy in range(2):
            for dx in range(2):
                tile = Image.open(ASSETS / "tiles/soil_tilled.png").convert("RGBA")
                canvas.alpha_composite(tile, ((bx + dx) * SIZE, (by + dy) * SIZE))
        # Continuous frame rails are one-pixel board faces with sturdy corner caps.
        ox, oy = bx * SIZE, by * SIZE
        d = ImageDraw.Draw(canvas)
        for py in (oy + 2, oy + 3, oy + 61, oy + 62):
            box(d, (ox + 2, py, ox + 61, py), "bark_dark" if py in (oy + 3, oy + 62) else "bark_light")
        for px in (ox + 2, ox + 3, ox + 61, ox + 62):
            box(d, (px, oy + 2, px, oy + 61), "bark_dark" if px in (ox + 3, ox + 62) else "bark_light")
        for xx, yy in ((ox + 5, oy + 5), (ox + 58, oy + 5), (ox + 5, oy + 58), (ox + 58, oy + 58)):
            box(d, (xx, yy, xx + 1, yy + 1), "sun")
        overlays.append({"type": "raised_bed", "x": bx, "y": by, "w": 2, "h": 2})
    # North fence and side returns, with a single walk-through gate along the south.
    fence_cells: set[tuple[int, int]] = {(x, 0) for x in range(1, 9)}
    fence_cells |= {(0, y) for y in range(1, 9)} | {(9, y) for y in range(1, 9)}
    fence_cells |= {(x, 9) for x in (1, 2, 3, 4, 6, 7, 8)}
    for x, y in sorted(fence_cells, key=lambda c: (c[1], c[0])):
        mask = 0
        for bit, (dx, dy) in ((1, (0, -1)), (2, (1, 0)), (4, (0, 1)), (8, (-1, 0))):
            if (x + dx, y + dy) in fence_cells:
                mask |= bit
        tile = Image.open(ASSETS / f"tiles/fence_auto_{mask:02}.png").convert("RGBA")
        canvas.alpha_composite(tile, (x * SIZE, y * SIZE))
    gate = Image.open(ASSETS / "tiles/fence_gate_open.png").convert("RGBA")
    canvas.alpha_composite(gate, (5 * SIZE, 9 * SIZE))
    overlays.extend({"type": "fence", "x": x, "y": y, "mask": sum(bit for bit, (dx, dy) in
                       ((1, (0, -1)), (2, (1, 0)), (4, (0, 1)), (8, (-1, 0))) if (x + dx, y + dy) in fence_cells)}
                    for x, y in sorted(fence_cells))
    overlays.append({"type": "gate_open", "x": 5, "y": 9})
    def place(rel: str, x: int, y: int, note: str = "") -> None:
        tile = Image.open(ASSETS / rel).convert("RGBA")
        canvas.alpha_composite(tile, (x * SIZE, y * SIZE))
        overlays.append({"type": rel, "x": x, "y": y, "note": note})
    # The greenhouse is a 2x2 tiled building. Its footprint remains separate from the ground.
    for name, x, y in (("greenhouse_nw", 7, 1), ("greenhouse_ne", 8, 1),
                       ("greenhouse_sw", 7, 2), ("greenhouse_se", 8, 2)):
        place(f"structures/{name}.png", x, y)
    # Two crop beds show contrasting mature stages and harvest colours.
    crop_layout = ((1, 5, "carrot", 4), (2, 5, "tomato", 4), (1, 6, "cabbage", 4),
                   (2, 6, "sunflower", 4), (3, 5, "tomato", 3), (4, 5, "carrot", 3),
                   (3, 6, "sunflower", 3), (4, 6, "cabbage", 3))
    for x, y, crop, stage in crop_layout:
        place(f"crops/crop_{crop}_stage_{stage:02}.png", x, y, f"{crop} stage {stage}")
    # Four flowers form one readable border cluster beside the orchard.
    place("flowers/flower_daisy_ivory_stage_03.png", 1, 3)
    place("flowers/flower_tulip_coral_stage_03.png", 2, 3)
    place("flowers/flower_bluebell_sky_stage_03.png", 3, 3)
    place("flowers/flower_cosmos_violet_stage_03.png", 4, 3)
    place("trees/tree_apple_01.png", 1, 1)
    place("trees/tree_pear_02.png", 3, 1)
    place("props/prop_signpost.png", 4, 8, "entry marker beside open south gate")
    place("props/prop_bench.png", 6, 5)
    place("props/prop_watering_can.png", 4, 7)
    place("props/prop_seed_bag.png", 3, 7)
    place("props/prop_terracotta_pot.png", 6, 4)
    place("props/prop_basket.png", 3, 8)
    place("props/prop_birdbath.png", 2, 8)
    place("props/prop_lily_pad.png", 7, 7, "pond surface accent")
    place("props/prop_pond_rock.png", 8, 6, "shoreline accent")
    place("critters/critter_butterfly.png", 4, 2)
    place("critters/critter_bee.png", 3, 2)
    place("critters/critter_snail.png", 8, 8)
    # Display at exact 3x nearest-neighbour scale for a crisp 1, 2, or 3x review.
    display = canvas.resize((canvas.width * SCALE, canvas.height * SCALE), Image.Resampling.NEAREST)
    display.save(ASSETS / "demo-scene.png", format="PNG", optimize=False)
    scene_map = {
        "name": "Cozy Garden v3 sample garden", "tile_size": [32, 32], "grid": [10, 10],
        "render_scale": SCALE, "layer_order": ["ground", "water", "paths", "soil and frames", "fence", "structures", "plants and props", "critters"],
        "ground": ground,
        "water_cells": [{"x": x, "y": y, "asset": f"tiles/water_auto_{sum(bit for bit, (dx, dy) in ((1, (0,-1)), (2,(1,0)), (4,(0,1)), (8,(-1,0))) if (x+dx,y+dy) in water_cells):02}.png"}
                         for x, y in sorted(water_cells, key=lambda c: (c[1], c[0]))],
        "path_cells": [{"x": x, "y": y, "asset": f"tiles/path_auto_{sum(bit for bit, (dx, dy) in ((1, (0,-1)), (2,(1,0)), (4,(0,1)), (8,(-1,0))) if (x+dx,y+dy) in path_cells):02}.png"}
                       for x, y in sorted(path_cells, key=lambda c: (c[1], c[0]))],
        "overlays": overlays,
        "note": "Each listed cell is 32x32; transparent sprites use bottom-center pivots unless atlas metadata says otherwise.",
    }
    (ASSETS / "demo-scene-map.json").write_text(json.dumps(scene_map, indent=2) + "\n", encoding="utf-8")


def wrap_label(text: str, max_chars: int = 25) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts = text.split("_")
    lines: list[str] = []
    current = ""
    for part in parts:
        addition = ("_" if current else "") + part
        if current and len(current) + len(addition) > max_chars:
            lines.append(current)
            current = part
        else:
            current += addition
    if current:
        lines.append(current)
    # Keep the common two-digit stage suffix attached to its word label.
    if len(lines) > 1 and len(lines[-1]) <= 3 and "_" in lines[-2]:
        previous, word = lines[-2].rsplit("_", 1)
        joined = word + "_" + lines[-1]
        if len(previous) <= max_chars and len(joined) <= max_chars:
            lines[-2:] = [previous, joined]
    if any(len(item) > max_chars for item in lines):
        lines = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
    return lines


def write_contact_sheet(records: list[dict]) -> None:
    cols, cell_w, cell_h, preview_scale = 6, 220, 198, 4
    groups = (
        ("GROUND / AUTOTILES", lambda p: p.startswith("tiles/")),
        ("TREES / STRUCTURES", lambda p: p.startswith(("trees/", "structures/"))),
        ("FLOWERS", lambda p: p.startswith("flowers/")),
        ("CROPS AND HARVESTS", lambda p: p.startswith("crops/")),
        ("PROPS / CRITTERS", lambda p: p.startswith(("props/", "critters/"))),
    )
    sections = [(title, [r for r in records if predicate(r["path"])]) for title, predicate in groups]
    header_h = 26
    height = 44 + sum(header_h + math.ceil(len(items) / cols) * cell_h for _, items in sections)
    sheet = Image.new("RGBA", (cols * cell_w, height), C["cream"])
    d = ImageDraw.Draw(sheet)
    pxtext(d, 10, 7, "COZY GARDEN V3 - 32X32 PIXEL ASSET PACK", "ink", 3)
    pxtext(d, 10, 27, f"{len(records)} PNGS - ORIGINAL CODE-DRAWN ART - 4X NEAREST PREVIEW", "ink_soft", 2)
    section_y = 44
    for title, items in sections:
        box(d, (0, section_y, cols * cell_w - 1, section_y + header_h - 2), "leaf_dark")
        pxtext(d, 10, section_y + 6, f"{title} - {len(items)} PNGS", "cream", 2)
        section_y += header_h
        for idx, record in enumerate(items):
            col, row = idx % cols, idx // cols
            x, y = col * cell_w, section_y + row * cell_h
            box(d, (x + 2, y + 2, x + cell_w - 3, y + cell_h - 3), "stone_light")
            box(d, (x + 4, y + 4, x + cell_w - 5, y + cell_h - 5), "cream")
            tile = Image.open(ASSETS / record["path"]).convert("RGBA")
            tile = tile.resize((SIZE * preview_scale, SIZE * preview_scale), Image.Resampling.NEAREST)
            sheet.alpha_composite(tile, (x + (cell_w - tile.width) // 2, y + 6))
            label = record["name"].upper()
            for line_no, label_line in enumerate(wrap_label(label)):
                pxtext(d, x + 5, y + 139 + line_no * 12, label_line, "ink", 2)
        section_y += math.ceil(len(items) / cols) * cell_h
    sheet.save(ASSETS / "preview-contact-sheet.png", format="PNG", optimize=False)


def write_readme(records: list[dict]) -> None:
    (ROOT / "README.md").write_text(f"""# Cozy Garden — 32×32 tiles & sprites (v3)

An original, code-drawn top-down pixel-art pack with **{len(records)} individual PNG sprites**. Every source sprite is 32×32 pixels, uses the bundled 36-colour palette plus transparency, and is drawn on an integer pixel grid without antialiasing. Light falls from the upper-left; shade falls to the lower-right. Near-black outlines are reserved for the greenhouse structure.

## Files

- `assets/tiles/` — 6 grass arrangements, soil/planter tiles, 4 stepping-stone variants, 16-way worn-earth path, 16-way water shore, and 16-way fence.
- `assets/flowers/` — 4 flower species × 2 colourways × 3 growth stages.
- `assets/crops/` — 4 crops × 4 growth stages plus 4 harvested items.
- `assets/structures/` — greenhouse, split into four 32×32 atlas pieces (assemble as a 2×2 block).
- `assets/props/`, `assets/critters/`, and `assets/trees/` — garden props and wildlife, including a lily pad and pond rock.
- `assets/tileset-sheet.png` — native 32px atlas; use `assets/tileset-sheet-map.json` for rectangles and names.
- `assets/demo-scene.png` — 10×10 garden, rendered at 3× with nearest-neighbour scaling; `demo-scene-map.json` records its layers and placements.
- `assets/tile-repeat-test.png` — an 8×8 grid of alternating grass arrangements rendered at 3× for repeat review.
- `assets/preview-contact-sheet.png` — labelled 4× overview with named ground, flower, crop, and prop sections; `assets/palette.png`, `palette.gpl`, and `palette.json` show the palette.
- `source/generate_pack.py` — deterministic generator and programmatic checks; `source/requirements.txt` lists the sole runtime dependency.

## Tilemap and engine setup

All ground, path, shore, and fence cells are 32×32. The `*_auto_NN.png` sets use a four-way bitmask: N=1, E=2, S=4, W=8; `NN` is the sum of connected cardinal neighbours from 00 through 15. Path and water tiles include the grass base; fence tiles have transparent backgrounds. For diagonal water corners, use the provided pixel chamfers and the cardinal map convention.

For **Godot**, set filtering to Nearest and use a 32×32 TileSet atlas region. Set collision shapes on fence cells and the greenhouse footprint as needed; the JSON manifest includes suggested collision/pivot notes. Place transparent plants/props above the ground and use bottom-centre pivots for upright objects.

For **Unity**, import individual PNGs as Sprites with Pixels Per Unit 32, Filter Mode Point, Compression None, and alpha transparency enabled. For the atlas choose Sprite Mode Multiple and slice on 32×32 cells; use the JSON map to identify cells. Ground sprites use a centered pivot; plants, props, trees and critters are intended to sit on a tile with a bottom-centre pivot. Keep atlas padding at zero or one pixel with no rotation.

Install the generator dependency with `python3 -m pip install -r source/requirements.txt`. Rebuild with `python3 source/generate_pack.py`; audit the current export with `python3 source/generate_pack.py --check`.
""", encoding="utf-8")


def alpha_topology(image: Image.Image) -> tuple[int, int]:
    """Return opaque connected components and enclosed transparent pixel count."""
    opaque = {(x, y) for y in range(SIZE) for x in range(SIZE) if image.getpixel((x, y))[3] == 255}
    unseen = set(opaque)
    components = 0
    while unseen:
        components += 1
        todo = deque([unseen.pop()])
        while todo:
            x, y = todo.popleft()
            for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if point in unseen:
                    unseen.remove(point)
                    todo.append(point)

    transparent = {(x, y) for y in range(SIZE) for x in range(SIZE) if image.getpixel((x, y))[3] == 0}
    outside = {point for point in transparent if point[0] in (0, SIZE - 1) or point[1] in (0, SIZE - 1)}
    todo = deque(outside)
    while todo:
        x, y = todo.popleft()
        for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if point in transparent and point not in outside:
                outside.add(point)
                todo.append(point)
    return components, len(transparent - outside)


def check_fence_topology() -> None:
    for mask in range(16):
        path = ASSETS / "tiles" / f"fence_auto_{mask:02}.png"
        image = Image.open(path).convert("RGBA")
        components, holes = alpha_topology(image)
        if components != 1 or holes:
            raise AssertionError(f"{path.name} has {components} opaque pieces and {holes} unintended alpha-hole pixels")
        pixels = image.load()
        if mask:
            if any(pixels[x, y][3] != 255 for y in range(12, 21) for x in range(14, 19)):
                raise AssertionError(f"{path.name} has a gap in the shared centre post")
            if any(pixels[x, 11] != C["cream"] for x in range(15, 18)):
                raise AssertionError(f"{path.name} has a misaligned or incomplete centre cap")
        else:
            if any(pixels[x, 14] != C["cream"] for x in range(15, 18)):
                raise AssertionError("fence_auto_00.png has an incomplete standalone-post cap")
        if mask & 1 and any(pixels[x, 0][3] != 255 for x in (10, 18)):
            raise AssertionError(f"{path.name} has an unaligned north rail")
        if mask & 1 and {x for x in range(SIZE) if pixels[x, 0][3] == 255} != set(range(10, 15)) | set(range(18, 23)):
            raise AssertionError(f"{path.name} north rail thickness differs from the shared five-pixel profile")
        if mask & 4 and any(pixels[x, 31][3] != 255 for x in (10, 18)):
            raise AssertionError(f"{path.name} has an unaligned south rail")
        if mask & 4 and {x for x in range(SIZE) if pixels[x, 31][3] == 255} != set(range(10, 15)) | set(range(18, 23)):
            raise AssertionError(f"{path.name} south rail thickness differs from the shared five-pixel profile")
        if mask & 8 and any(pixels[0, y][3] != 255 for y in (10, 20)):
            raise AssertionError(f"{path.name} has an unaligned west rail")
        if mask & 8 and {y for y in range(SIZE) if pixels[0, y][3] == 255} != set(range(10, 15)) | set(range(20, 25)):
            raise AssertionError(f"{path.name} west rail thickness differs from the shared five-pixel profile")
        if mask & 2 and any(pixels[31, y][3] != 255 for y in (10, 20)):
            raise AssertionError(f"{path.name} has an unaligned east rail")
        if mask & 2 and {y for y in range(SIZE) if pixels[31, y][3] == 255} != set(range(10, 15)) | set(range(20, 25)):
            raise AssertionError(f"{path.name} east rail thickness differs from the shared five-pixel profile")
    opened = Image.open(ASSETS / "tiles/fence_gate_open.png").convert("RGBA")
    closed = Image.open(ASSETS / "tiles/fence_gate_closed.png").convert("RGBA")
    if opened.getpixel((12, 21))[3] != 0 or opened.getpixel((25, 25))[3] != 255:
        raise AssertionError("open gate must leave a walk-through gap and show its swung leaf")
    if any(opened.getpixel((x, y))[3] != 0 for y in range(10, 24) for x in range(12, 20)):
        raise AssertionError("open gate leaf or rail blocks the path-to-fence entrance")
    if closed.getpixel((12, 21))[3] != 255 or closed.getpixel((23, 16))[3] != 255:
        raise AssertionError("closed gate must have a continuous barrier and visible stiles")


def check_path_connectivity() -> None:
    for mask in range(16):
        name = f"path_auto_{mask:02}.png"
        image = Image.open(ASSETS / "tiles" / name).convert("RGBA")
        if image.tobytes() != path_tile(mask).tobytes():
            raise AssertionError(f"{name} does not match its fixed earth-path mask")
        pixels = image.load()
        earth = {(x, y) for y in range(SIZE) for x in range(SIZE) if pixels[x, y] in PATH_COLORS}
        if not earth:
            raise AssertionError(f"{name} has no earth-path pixels")
        unseen = set(earth)
        components = 0
        while unseen:
            components += 1
            todo = deque([unseen.pop()])
            while todo:
                x, y = todo.popleft()
                for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if point in unseen:
                        unseen.remove(point)
                        todo.append(point)
        if components != 1:
            raise AssertionError(f"{name} splits into {components} disconnected earth pieces")
        edges = {
            1: {(x, 0) for x in range(SIZE)},
            2: {(SIZE - 1, y) for y in range(SIZE)},
            4: {(x, SIZE - 1) for x in range(SIZE)},
            8: {(0, y) for y in range(SIZE)},
        }
        for bit, edge in edges.items():
            contact = earth & edge
            if mask & bit and len(contact) < 7:
                raise AssertionError(f"{name} has a narrow or missing {bit}-side path join")
            if not mask & bit and contact:
                raise AssertionError(f"{name} spills onto its unconnected {bit}-side edge")


def check_directional_shading(path: Path, image: Image.Image) -> None:
    folder = path.parent.name
    pixels = image.load()
    opaque = [(x, y) for y in range(SIZE) for x in range(SIZE) if pixels[x, y][3] == 255]
    if folder != "structures":
        if any(pixels[x, y] in NEAR_BLACK_OUTLINE_SWATCHES for x, y in opaque):
            raise AssertionError(f"{path.relative_to(ASSETS)} uses near-black ink outside a structure")
    if folder not in OBJECT_FOLDERS or not opaque:
        return
    min_x, max_x = min(x for x, _ in opaque), max(x for x, _ in opaque)
    min_y, max_y = min(y for _, y in opaque), max(y for _, y in opaque)
    mid_x, mid_y = (min_x + max_x) // 2, (min_y + max_y) // 2
    lit_upper_left = any(pixels[x, y] in LIGHT_SWATCHES and x <= mid_x and y <= mid_y for x, y in opaque)
    shaded_lower_right = any(pixels[x, y] in SHADE_SWATCHES and x >= mid_x and y >= mid_y for x, y in opaque)
    if not lit_upper_left or not shaded_lower_right:
        raise AssertionError(f"{path.relative_to(ASSETS)} violates {SHADING_RULE['light']} light / {SHADING_RULE['shade']} shade")


def check_pack(expected_records: list[dict] | None = None) -> dict:
    sprite_files = sorted(path for folder in ("tiles", "flowers", "crops", "props", "critters", "trees", "structures")
                          for path in (ASSETS / folder).glob("*.png"))
    if not sprite_files:
        raise AssertionError("no individual sprite PNGs found")
    allowed = {TRANSPARENT, *C.values()}
    colors: set[tuple[int, int, int, int]] = {TRANSPARENT}
    for path in sprite_files:
        im = Image.open(path).convert("RGBA")
        if im.size != (32, 32):
            raise AssertionError(f"{path.relative_to(ASSETS)} is {im.size}; every source sprite must be 32x32")
        pixels = [im.getpixel((x, y)) for y in range(SIZE) for x in range(SIZE)]
        alphas = {pixel[3] for pixel in pixels}
        if not alphas <= {0, 255}:
            raise AssertionError(f"{path.name} contains partially-transparent/antialiased pixels: {alphas}")
        used = set(pixels)
        unexpected = used - allowed
        if unexpected:
            raise AssertionError(f"{path.name} uses colours outside the shared palette: {unexpected}")
        colors.update(used)
        check_directional_shading(path, im)
    if len(colors) > 40:
        raise AssertionError(f"palette count is {len(colors)}, above the 40-colour limit")
    for family in ("path", "water", "fence"):
        actual = {int(path.stem.rsplit("_", 1)[1]) for path in (ASSETS / "tiles").glob(f"{family}_auto_*.png")}
        if actual != set(range(16)):
            raise AssertionError(f"{family} cardinal autotile masks are incomplete: {sorted(actual)}")
    check_fence_topology()
    check_path_connectivity()
    if set(shape for shape, _ in REFLECTION_MASK_MAP) != set(range(len(REFLECTION_NAMES))):
        raise AssertionError("water masks must distribute all three dark reflection silhouettes")
    if set(rotation for _, rotation in REFLECTION_MASK_MAP) != set(range(4)):
        raise AssertionError("water reflection marks must include all four fixed rotations")
    for mask in range(16):
        if len(RIPPLE_LAYOUTS[mask % len(RIPPLE_LAYOUTS)]) not in range(2, 5):
            raise AssertionError(f"water mask {mask:02} has no documented 2–4 ripple marks")
        exported = Image.open(ASSETS / "tiles" / f"water_auto_{mask:02}.png").convert("RGBA")
        if exported.tobytes() != water_tile(mask).tobytes():
            raise AssertionError(f"water_auto_{mask:02}.png does not match its documented ripple placement")
    grass_count = len(list((ASSETS / "tiles").glob("grass_*.png")))
    if grass_count != len(GRASS_VARIANTS) or grass_count != 6 or len(list((ASSETS / "tiles").glob("stone_path_*.png"))) != 4:
        raise AssertionError("ground variants must include six grass arrangements and four stepping-stone tiles")
    if len({grass_tile(kind).tobytes() for kind in GRASS_VARIANTS}) != len(GRASS_VARIANTS):
        raise AssertionError("grass arrangements must be visually distinct")
    if set(GRASS_DENSITY.values()) != {"sparse", "medium", "dense"}:
        raise AssertionError("grass arrangements must cover sparse, medium, and dense densities")
    repeat_layout = [[grass_repeat_variant(x, y) for x in range(8)] for y in range(8)]
    if set(value for row in repeat_layout for value in row) != set(range(len(GRASS_VARIANTS))) or any(
            repeat_layout[y][x] == repeat_layout[y][x + 1] for y in range(8) for x in range(7)) or any(
            repeat_layout[y][x] == repeat_layout[y + 1][x] for y in range(7) for x in range(8)):
        raise AssertionError("grass repeat layout must alternate all six arrangements without adjacent duplicates")
    wet = Image.open(ASSETS / "tiles/soil_wet.png").convert("RGBA")
    tilled = Image.open(ASSETS / "tiles/soil_tilled.png").convert("RGBA")
    if sum(wet.getpixel((x, y)) != tilled.getpixel((x, y))
           for y in range(SIZE) for x in range(SIZE)) < 24:
        raise AssertionError("wet soil must remain visibly distinct from tilled soil")
    if len(list((ASSETS / "trees").glob("*.png"))) != 2 or len(list((ASSETS / "structures").glob("*.png"))) != 4:
        raise AssertionError("the pack must include two trees and all four greenhouse atlas pieces")
    if not (ASSETS / "props/prop_lily_pad.png").is_file() or not (ASSETS / "props/prop_pond_rock.png").is_file():
        raise AssertionError("the pack must include its lily-pad and pond-rock sprites")
    atlas = Image.open(ASSETS / "tileset-sheet.png")
    if atlas.width % SIZE or atlas.height % SIZE:
        raise AssertionError(f"atlas is not on a 32px grid: {atlas.size}")
    contact = Image.open(ASSETS / "preview-contact-sheet.png")
    if contact.width % 220:
        raise AssertionError(f"contact sheet cells are not evenly laid out: {contact.size}")
    scene = Image.open(ASSETS / "demo-scene.png")
    if scene.size != (10 * SIZE * SCALE, 10 * SIZE * SCALE):
        raise AssertionError(f"demo scene is not a 10x10 grid at {SCALE}x: {scene.size}")
    scene_map = json.loads((ASSETS / "demo-scene-map.json").read_text(encoding="utf-8"))
    if scene_map.get("grid") != [10, 10] or len(scene_map.get("ground", [])) != 10 or any(len(row) != 10 for row in scene_map["ground"]):
        raise AssertionError("demo scene map does not describe an aligned 10x10 layer")
    overlay_paths = {item.get("type") for item in scene_map.get("overlays", [])}
    if len(scene_map.get("water_cells", [])) < 6 or not {
            "props/prop_lily_pad.png", "props/prop_pond_rock.png", "gate_open"}.issubset(overlay_paths):
        raise AssertionError("v3 demo must rebuild the organic pond, water accents, and clear entrance")
    atlas_map = json.loads((ASSETS / "tileset-sheet-map.json").read_text(encoding="utf-8"))
    if atlas_map.get("art_direction") != SHADING_RULE:
        raise AssertionError("atlas manifest does not document the enforced shading rule")
    water_rule = atlas_map.get("water_detail_rule", {})
    if water_rule.get("ripple_marks_per_tile") != 3 or "fixed mask-indexed offsets" not in water_rule.get("placement", ""):
        raise AssertionError("atlas manifest does not document fixed ripple placement")
    expected_reflections = {f"{mask:02}": {"shape": REFLECTION_NAMES[shape], "rotation_degrees": rotation * 90}
                            for mask, (shape, rotation) in enumerate(REFLECTION_MASK_MAP)}
    if water_rule.get("reflection_mapping") != expected_reflections:
        raise AssertionError("atlas manifest does not document the three rotated reflection shapes by mask")
    expected_grass = {f"tiles/grass_{kind}.png": {"density": density}
                      for kind, density in GRASS_DENSITY.items()}
    if atlas_map.get("grass_arrangements") != expected_grass:
        raise AssertionError("atlas manifest does not document all grass arrangements and densities")
    if len(atlas_map.get("assets", [])) != len(sprite_files):
        raise AssertionError("atlas map entry count does not match individual sprite PNGs")
    atlas_paths = {record["path"] for record in atlas_map["assets"]}
    exported_paths = {path.relative_to(ASSETS).as_posix() for path in sprite_files}
    if atlas_paths != exported_paths:
        raise AssertionError("atlas map paths do not match exported individual PNGs")
    for index, record in enumerate(atlas_map["assets"]):
        expected_rect = {"x": (index % atlas_map["columns"]) * SIZE,
                         "y": (index // atlas_map["columns"]) * SIZE,
                         "w": SIZE, "h": SIZE, "index": index}
        if record.get("atlas") != expected_rect:
            raise AssertionError(f"atlas location for {record['path']} is not cell-aligned")
    names = {path.stem for path in sprite_files}
    if expected_records and names != {record["name"] for record in expected_records}:
        raise AssertionError("manifested names do not match exported sprite names")
    if len(list((ASSETS / "flowers").glob("*.png"))) != 24:
        raise AssertionError("flower coverage must be 4 species x 2 colours x 3 stages")
    seedlings = [flower_tile(species, "cream", "sun", 1).tobytes()
                 for species in ("daisy", "tulip", "bluebell", "cosmos")]
    if len(set(seedlings)) != 4:
        raise AssertionError("stage-1 flower sprouts must vary by species")
    if len(list((ASSETS / "crops").glob("crop_*.png"))) != 16 or len(list((ASSETS / "crops").glob("harvest_*.png"))) != 4:
        raise AssertionError("crop coverage must be 4 crops x 4 stages plus 4 harvested items")
    for crop in ("carrot", "tomato", "cabbage", "sunflower"):
        stages = [Image.open(ASSETS / "crops" / f"crop_{crop}_stage_{stage:02}.png").convert("RGBA")
                  for stage in range(1, 5)]
        if len({image.tobytes() for image in stages}) != 4:
            raise AssertionError(f"{crop} growth stages are not four distinct sprites")
    repeat_path = ASSETS / "tile-repeat-test.png"
    if not repeat_path.is_file():
        raise AssertionError("8x8 grass tile repeat preview is missing")
    repeat = Image.open(repeat_path).convert("RGBA")
    if repeat.size != (8 * SIZE * SCALE, 8 * SIZE * SCALE):
        raise AssertionError(f"grass repeat preview must be an 8x8 grid at {SCALE}x: {repeat.size}")
    if repeat.tobytes() != grass_repeat_test_image().tobytes():
        raise AssertionError("grass repeat preview does not match the alternating six-variant grid")
    contact = Image.open(ASSETS / "preview-contact-sheet.png").convert("RGBA")
    tile_rows = math.ceil(len(list((ASSETS / "tiles").glob("*.png"))) / 6)
    structure_rows = math.ceil((len(list((ASSETS / "trees").glob("*.png"))) +
                                 len(list((ASSETS / "structures").glob("*.png")))) / 6)
    flowers_y = 44 + 26 + tile_rows * 198 + 26 + structure_rows * 198
    crops_y = flowers_y + 26 + math.ceil(24 / 6) * 198
    if any(contact.getpixel((0, y)) != C["leaf_dark"] for y in (44, flowers_y, crops_y)):
        raise AssertionError("contact sheet flower or crop section headers are missing")
    meta_images = [ASSETS / "tileset-sheet.png", ASSETS / "demo-scene.png",
                   ASSETS / "preview-contact-sheet.png", ASSETS / "palette.png", repeat_path]
    for path in meta_images:
        im = Image.open(path).convert("RGBA")
        histogram = im.getcolors(maxcolors=64)
        if histogram is None:
            raise AssertionError(f"{path.name} uses more than 64 unique colours")
        meta_colors = {color for _, color in histogram}
        if not meta_colors <= allowed:
            raise AssertionError(f"{path.name} uses colours outside the shared palette")
        if {pixel[3] for pixel in meta_colors} - {0, 255}:
            raise AssertionError(f"{path.name} uses antialiased/partial alpha")
        colors.update(meta_colors)
    if len(colors) > 40:
        raise AssertionError(f"combined pack uses {len(colors)} colours, above the 40-colour limit")
    return {"sprites": len(sprite_files), "palette_colours_including_transparent": len(colors),
            "atlas_grid": [atlas.width // SIZE, atlas.height // SIZE], "scene_pixels": list(scene.size)}


def main() -> int:
    if "--check" in sys.argv[1:]:
        result = check_pack()
        print(f"CHECK OK: {result['sprites']} sprites; {result['palette_colours_including_transparent']}/40 colours; 32px source grid; 10x10 scene; 8x8 grass repeat at 3x")
        return 0
    for folder in ("tiles", "flowers", "crops", "props", "critters", "trees", "structures"):
        (ASSETS / folder).mkdir(parents=True, exist_ok=True)
    records = build_sprites()
    write_palette()
    write_tile_repeat_test()
    write_atlas(records)
    draw_scene(records)
    write_contact_sheet(records)
    write_readme(records)
    result = check_pack(records)
    print(f"BUILD OK: {result['sprites']} sprites; {result['palette_colours_including_transparent']}/40 colours; 32px source grid; 10x10 scene; 8x8 grass repeat at 3x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
