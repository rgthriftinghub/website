"""Generate editorial figure art for the storefront.

**Why this exists.** The site needs model imagery — people wearing clothes — and
real fashion photography is copyrighted. Rather than scrape someone's shoot, this
draws original, stylised fashion illustrations in the RG palette: elongated
figures, flat tonal garment blocks, paper grain. It is the look of a hand-drawn
lookbook plate, which sits honestly beside a thrift brand and is owned outright.

These are placeholders with intent, not pretend photographs. When the client
supplies a real shoot, drop the files into the same paths and nothing else changes.

Run:  python scripts/generate_editorial_images.py
Out:  frontend/public/editorial/*.jpg
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

OUT_DIR = Path(__file__).resolve().parents[2] / "frontend" / "public" / "editorial"

# Brand palette, matching globals.css.
INK = (14, 13, 12)
INK_SOFT = (28, 26, 24)
GOLD = (195, 154, 81)
GOLD_SOFT = (227, 207, 166)
GOLD_WASH = (246, 239, 225)
PAPER = (250, 248, 244)
PAPER_ALT = (243, 239, 232)
STONE = (140, 132, 122)

# Supersampling factor. Everything is drawn large then downscaled, which is what
# gives the curves clean anti-aliased edges instead of stair-stepping.
SS = 3


@dataclass(frozen=True)
class Palette:
    """One plate's colour scheme."""

    bg_top: tuple[int, int, int]
    bg_bottom: tuple[int, int, int]
    skin: tuple[int, int, int]
    hair: tuple[int, int, int]
    garment: tuple[int, int, int]
    garment_shade: tuple[int, int, int]
    accent: tuple[int, int, int]
    figure: tuple[int, int, int] = (26, 23, 21)

    def flattened(self) -> "Palette":
        """Same palette with every figure colour collapsed to the silhouette tone."""
        return Palette(
            self.bg_top, self.bg_bottom, self.figure, self.figure,
            self.figure, self.figure, self.accent, self.figure,
        )


# Warm, muted schemes. Deliberately few and closely related so a wall of these
# reads as one collection rather than a colour test card.
PALETTES: list[Palette] = [
    Palette(GOLD_WASH, (232, 219, 196), (214, 176, 142), (46, 36, 30), (38, 46, 62), (28, 34, 48), GOLD, (24, 22, 20)),
    Palette((238, 231, 220), (219, 208, 192), (198, 156, 120), (30, 26, 24), (122, 46, 38), (96, 34, 28), GOLD_SOFT, (104, 38, 32)),
    Palette((226, 222, 214), (203, 197, 186), (222, 186, 152), (52, 40, 32), (58, 66, 58), (42, 50, 44), GOLD, (44, 52, 46)),
    Palette((243, 236, 224), (226, 212, 188), (190, 148, 114), (26, 22, 20), (72, 78, 96), (54, 60, 76), GOLD_SOFT, (38, 44, 58)),
    Palette((231, 224, 212), (208, 196, 178), (210, 170, 136), (40, 32, 28), (150, 116, 66), (120, 92, 50), INK, (110, 84, 44)),
    Palette((222, 216, 208), (196, 188, 176), (204, 162, 128), (34, 28, 26), (44, 44, 48), (32, 32, 36), GOLD, (26, 24, 22)),
]


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))  # type: ignore[return-value]


def _gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    """Vertical gradient ground."""
    width, height = size
    base = Image.new("RGB", (1, height))
    pixels = base.load()
    for y in range(height):
        pixels[0, y] = _lerp(top, bottom, y / max(height - 1, 1))
    return base.resize(size, Image.Resampling.BILINEAR)


def _soft_shadow(
    canvas: Image.Image, shape: list[tuple[float, float]], blur: int = 26, alpha: int = 46
) -> None:
    """Drop a blurred dark shape behind a figure so it sits on the ground."""
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(shape, fill=(0, 0, 0, alpha))
    canvas.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def _ellipse(draw: ImageDraw.ImageDraw, cx: float, cy: float, rx: float, ry: float, fill) -> None:
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=fill)


def _limb(
    draw: ImageDraw.ImageDraw,
    start: tuple[float, float],
    end: tuple[float, float],
    w_start: float,
    w_end: float,
    fill,
) -> None:
    """A tapered limb: a quad plus rounded caps, so joints read as joints."""
    (x1, y1), (x2, y2) = start, end
    angle = math.atan2(y2 - y1, x2 - x1) + math.pi / 2
    dx1, dy1 = math.cos(angle) * w_start / 2, math.sin(angle) * w_start / 2
    dx2, dy2 = math.cos(angle) * w_end / 2, math.sin(angle) * w_end / 2
    draw.polygon(
        [
            (x1 - dx1, y1 - dy1),
            (x1 + dx1, y1 + dy1),
            (x2 + dx2, y2 + dy2),
            (x2 - dx2, y2 - dy2),
        ],
        fill=fill,
    )
    _ellipse(draw, x1, y1, w_start / 2, w_start / 2, fill)
    _ellipse(draw, x2, y2, w_end / 2, w_end / 2, fill)


def _grain(canvas: Image.Image, strength: int = 9) -> Image.Image:
    """Fine monochrome noise. The single biggest thing separating a flat vector
    fill from something that looks printed."""
    width, height = canvas.size
    rng = random.Random(0xC39A51)
    noise = Image.new("L", (width // 2, height // 2))
    noise.putdata([128 + rng.randint(-strength, strength) for _ in range(noise.width * noise.height)])
    noise = noise.resize(canvas.size, Image.Resampling.BILINEAR)
    return Image.blend(canvas, Image.merge("RGB", (noise, noise, noise)), 0.055)


def _vignette(canvas: Image.Image, strength: float = 0.30) -> Image.Image:
    width, height = canvas.size
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).ellipse(
        [-width * 0.25, -height * 0.18, width * 1.25, height * 1.18], fill=255
    )
    mask = mask.filter(ImageFilter.GaussianBlur(min(width, height) // 7))
    dark = Image.new("RGB", (width, height), INK)
    return Image.composite(canvas, Image.blend(canvas, dark, strength), mask)


# --------------------------------------------------------------------- figures
def _draw_figure(
    draw: ImageDraw.ImageDraw,
    cx: float,
    top: float,
    height: float,
    palette: Palette,
    *,
    garment: str,
    feminine: bool,
    pose: int,
) -> None:
    """Draw one elongated figure.

    Proportions are roughly nine heads rather than a realistic seven and a half —
    the standard fashion-illustration exaggeration, which is what makes clothes
    read as styled rather than merely worn.
    """
    head_h = height / 9.0
    head_w = head_h * 0.66

    # Vertical landmarks.
    head_cy = top + head_h * 0.55
    shoulder_y = top + head_h * 1.45
    bust_y = top + head_h * 2.35
    waist_y = top + head_h * 3.45
    hip_y = top + head_h * 4.35
    knee_y = top + head_h * 6.4
    ankle_y = top + head_h * 8.55

    # A slight contrapposto sway keeps the figure from looking like a mannequin.
    sway = head_w * (0.16 if pose % 2 == 0 else -0.16)
    hip_cx = cx + sway
    shoulder_w = head_w * (1.55 if feminine else 1.95)
    hip_w = head_w * (1.62 if feminine else 1.45)

    # One tone for the whole figure.
    skin = palette.figure
    skin_shade = palette.figure
    palette = palette.flattened()

    # ---- legs -----------------------------------------------------------
    leg_gap = hip_w * 0.34
    for side in (-1, 1):
        hx = hip_cx + side * leg_gap
        kx = hx + side * head_w * 0.06 + (sway * 0.3)
        ax = kx - side * head_w * 0.02
        _limb(draw, (hx, hip_y), (kx, knee_y), head_w * 0.62, head_w * 0.44, skin)
        _limb(draw, (kx, knee_y), (ax, ankle_y), head_w * 0.44, head_w * 0.30, skin)
        # foot
        _ellipse(draw, ax, ankle_y + head_h * 0.10, head_w * 0.17, head_h * 0.10, skin_shade)

    # ---- torso -----------------------------------------------------------
    torso = [
        (cx - shoulder_w * 0.5, shoulder_y),
        (cx + shoulder_w * 0.5, shoulder_y),
        (cx + shoulder_w * 0.42, bust_y),
        (hip_cx + hip_w * 0.5, waist_y),
        (hip_cx + hip_w * 0.56, hip_y),
        (hip_cx - hip_w * 0.56, hip_y),
        (hip_cx - hip_w * 0.5, waist_y),
        (cx - shoulder_w * 0.42, bust_y),
    ]
    draw.polygon(torso, fill=skin)

    # ---- trousers / skirt ------------------------------------------------
    if garment in ("jeans", "trousers"):
        for side in (-1, 1):
            hx = hip_cx + side * leg_gap
            kx = hx + side * head_w * 0.06 + (sway * 0.3)
            ax = kx - side * head_w * 0.02
            _limb(draw, (hx, hip_y - head_h * 0.1), (kx, knee_y), head_w * 0.62, head_w * 0.42, palette.garment)
            _limb(draw, (kx, knee_y), (ax, ankle_y + head_h * 0.02), head_w * 0.42, head_w * 0.30, palette.garment)
        # seat block joining the legs
        draw.polygon(
            [
                (hip_cx - hip_w * 0.62, waist_y),
                (hip_cx + hip_w * 0.62, waist_y),
                (hip_cx + hip_w * 0.58, hip_y + head_h * 0.15),
                (hip_cx - hip_w * 0.58, hip_y + head_h * 0.15),
            ],
            fill=palette.garment,
        )
    elif garment in ("dress", "abaya", "kurta", "skirt"):
        hem = ankle_y - head_h * (0.4 if garment in ("dress", "abaya") else 2.6)
        flare = hip_w * (1.5 if garment in ("dress", "abaya") else 1.15)
        draw.polygon(
            [
                (cx - shoulder_w * 0.52, shoulder_y + head_h * 0.1),
                (cx + shoulder_w * 0.52, shoulder_y + head_h * 0.1),
                (hip_cx + flare, hem),
                (hip_cx - flare, hem),
            ],
            fill=palette.garment,
        )
        # a fold, for a little drape
        draw.polygon(
            [
                (cx + shoulder_w * 0.1, shoulder_y + head_h * 0.2),
                (cx + shoulder_w * 0.4, shoulder_y + head_h * 0.2),
                (hip_cx + flare * 0.72, hem),
                (hip_cx + flare * 0.24, hem),
            ],
            fill=palette.garment_shade,
        )

    # ---- upper garment ---------------------------------------------------
    if garment in ("jeans", "trousers", "shirt", "t_shirt", "polo", "sweater", "jacket", "coat", "hoodie"):
        length = {
            "coat": hip_y + head_h * 1.5,
            "jacket": hip_y + head_h * 0.3,
            "hoodie": hip_y + head_h * 0.2,
            "sweater": hip_y,
        }.get(garment, waist_y + head_h * 0.5)

        top_shape = [
            (cx - shoulder_w * 0.54, shoulder_y - head_h * 0.06),
            (cx + shoulder_w * 0.54, shoulder_y - head_h * 0.06),
            (cx + shoulder_w * 0.5, bust_y),
            (hip_cx + hip_w * 0.58, length),
            (hip_cx - hip_w * 0.58, length),
            (cx - shoulder_w * 0.5, bust_y),
        ]
        draw.polygon(top_shape, fill=palette.garment)

        # Lapel / placket, which is what makes it read as a specific garment
        # rather than a coloured blob.
        if garment in ("coat", "jacket"):
            draw.polygon(
                [
                    (cx - shoulder_w * 0.16, shoulder_y),
                    (cx + shoulder_w * 0.16, shoulder_y),
                    (cx + shoulder_w * 0.05, bust_y + head_h * 0.5),
                    (cx - shoulder_w * 0.05, bust_y + head_h * 0.5),
                ],
                fill=palette.garment_shade,
            )
            draw.line(
                [(cx, shoulder_y), (cx, length)], fill=palette.garment_shade, width=int(head_w * 0.07)
            )
        elif garment in ("shirt", "polo"):
            draw.line(
                [(cx, shoulder_y), (cx, length)], fill=palette.garment_shade, width=int(head_w * 0.06)
            )

    # ---- arms ------------------------------------------------------------
    sleeve = garment in ("coat", "jacket", "sweater", "hoodie", "shirt", "abaya", "kurta")
    arm_fill = palette.garment if sleeve else skin
    for side in (-1, 1):
        sx = cx + side * shoulder_w * 0.5
        # One arm relaxed, one slightly out — a pose, not a T.
        out = 1.22 if (side > 0) == (pose % 2 == 0) else 0.92
        ex = sx + side * head_w * 0.34 * out
        ey = bust_y + head_h * 0.72
        wx = ex + side * head_w * 0.12 * out
        wy = waist_y + head_h * 0.78
        _limb(draw, (sx, shoulder_y + head_h * 0.1), (ex, ey), head_w * 0.46, head_w * 0.34, arm_fill)
        _limb(draw, (ex, ey), (wx, wy), head_w * 0.34, head_w * 0.25, arm_fill if garment != "t_shirt" else skin)
        _ellipse(draw, wx, wy + head_h * 0.10, head_w * 0.13, head_h * 0.11, skin)

    # ---- neck + head -----------------------------------------------------
    _limb(draw, (cx, shoulder_y - head_h * 0.02), (cx, head_cy + head_h * 0.34), head_w * 0.30, head_w * 0.26, skin_shade)
    _ellipse(draw, cx, head_cy, head_w * 0.47, head_h * 0.56, skin)

    # Hair.
    #
    # Kept inside the silhouette of the skull and shoulders. An earlier version
    # squared off above the crown and flared wider than the head, which read as
    # antennae at small sizes rather than hair.
    if feminine:
        draw.polygon(
            [
                (cx - head_w * 0.47, head_cy - head_h * 0.10),
                (cx - head_w * 0.50, head_cy + head_h * 0.20),
                (cx - head_w * 0.42, shoulder_y - head_h * 0.06),
                (cx - head_w * 0.22, shoulder_y - head_h * 0.06),
                (cx - head_w * 0.26, head_cy + head_h * 0.12),
                (cx + head_w * 0.26, head_cy + head_h * 0.12),
                (cx + head_w * 0.22, shoulder_y - head_h * 0.06),
                (cx + head_w * 0.42, shoulder_y - head_h * 0.06),
                (cx + head_w * 0.50, head_cy + head_h * 0.20),
                (cx + head_w * 0.47, head_cy - head_h * 0.10),
            ],
            fill=palette.hair,
        )
    # Crown: sits on the skull, never above it.
    _ellipse(draw, cx, head_cy - head_h * 0.08, head_w * 0.48, head_h * 0.46, palette.hair)


# ------------------------------------------------------------------- plates
@dataclass(frozen=True)
class Plate:
    name: str
    garment: str
    feminine: bool
    width: int
    height: int
    palette_index: int


PLATES: list[Plate] = [
    # Women — the majority, as asked.
    Plate("women-coat-01", "coat", True, 1000, 1250, 3),
    Plate("women-dress-01", "dress", True, 1000, 1250, 1),
    Plate("women-abaya-01", "abaya", True, 1000, 1250, 5),
    Plate("women-kurta-01", "kurta", True, 1000, 1250, 4),
    Plate("women-jeans-01", "jeans", True, 1000, 1250, 0),
    Plate("women-sweater-01", "sweater", True, 1000, 1250, 2),
    Plate("women-jacket-01", "jacket", True, 1000, 1250, 3),
    Plate("women-skirt-01", "skirt", True, 1000, 1250, 1),
    # Men.
    Plate("men-coat-01", "coat", False, 1000, 1250, 5),
    Plate("men-jeans-01", "jeans", False, 1000, 1250, 0),
    Plate("men-shirt-01", "shirt", False, 1000, 1250, 2),
    Plate("men-jacket-01", "jacket", False, 1000, 1250, 3),
    Plate("men-hoodie-01", "hoodie", False, 1000, 1250, 4),
    Plate("men-kurta-01", "kurta", False, 1000, 1250, 1),
    # Wide hero crops.
    Plate("hero-women-01", "coat", True, 1400, 1750, 3),
    Plate("hero-men-01", "jacket", False, 1400, 1750, 5),
]


def render_plate(plate: Plate) -> Image.Image:
    """Compose one plate.

    Composition notes, which is where the "premium" actually comes from:

    * The figure is drawn ~1.9x the frame height and cropped at the knee. Tight
      crops are what lookbooks do — they put the garment in the frame rather than
      a small person in a large empty room.
    * It sits off-centre on a two-tone ground, so the negative space is deliberate
      instead of leftover.
    * A soft directional light and a darker side on the garment give form; flat
      fills are what made the first pass look like clip art.
    """
    palette = PALETTES[plate.palette_index % len(PALETTES)]
    width, height = plate.width * SS, plate.height * SS
    rng = random.Random(hash(plate.name) & 0xFFFF)

    canvas = _gradient((width, height), palette.bg_top, palette.bg_bottom).convert("RGBA")

    # Colour block: a vertical band occupying roughly a third, on the side the
    # figure is not on. Gives the composition a spine.
    left_figure = rng.random() < 0.5
    band = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bx = (width * 0.58, width) if left_figure else (0, width * 0.42)
    ImageDraw.Draw(band).rectangle([bx[0], 0, bx[1], height], fill=(*palette.accent, 30))
    canvas.alpha_composite(band)

    # Horizon line: a subtle floor/wall split, low in frame.
    horizon = height * 0.80
    floor = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(floor).rectangle(
        [0, horizon, width, height], fill=(*_lerp(palette.bg_bottom, INK, 0.10), 200)
    )
    canvas.alpha_composite(floor.filter(ImageFilter.GaussianBlur(width // 200)))

    # Studio halo behind the figure.
    cx = width * (0.40 if left_figure else 0.60)
    halo = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(halo).ellipse(
        [cx - width * 0.40, -height * 0.10, cx + width * 0.40, height * 0.78],
        fill=(*palette.accent, 46),
    )
    canvas.alpha_composite(halo.filter(ImageFilter.GaussianBlur(width // 10)))

    # Figure: oversized and cropped. Head sits just inside the top edge; the
    # bottom of the frame cuts across the lower thigh.
    figure_height = height * 0.88
    figure_top = height * 0.06

    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    _draw_figure(
        ImageDraw.Draw(layer),
        cx,
        figure_top,
        figure_height,
        palette,
        garment=plate.garment,
        feminine=plate.feminine,
        pose=hash(plate.name) % 2,
    )

    canvas.alpha_composite(layer)

    out = canvas.convert("RGB").resize((plate.width, plate.height), Image.Resampling.LANCZOS)
    out = _vignette(out, 0.26)
    return _grain(out)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for plate in PLATES:
        image = render_plate(plate)
        path = OUT_DIR / f"{plate.name}.jpg"
        image.save(path, "JPEG", quality=88, optimize=True, progressive=True)
        print(f"  {path.name:28} {plate.width}x{plate.height}  {path.stat().st_size // 1024} KB")
    print(f"\n{len(PLATES)} editorial plates written to {OUT_DIR}")


if __name__ == "__main__":
    main()


# --------------------------------------------------- category cards (overwrite)
# The seeded category images were abstract dark plates from an earlier phase. Now
# that the homepage is editorial, those three cards were the one inconsistent
# block, so they are regenerated here in the same style and written over the
# originals. Paths are unchanged, so no seed or database edit is needed.
CATEGORY_PLATES = [
    ("men", "men-jacket-01", 5),
    ("women", "women-coat-01", 3),
    ("accessories", "women-sweater-01", 4),
]


def render_category_cards() -> None:
    demo_dir = Path(__file__).resolve().parents[2] / "frontend" / "public" / "demo" / "categories"
    if not demo_dir.exists():
        return
    for slug, source, palette_index in CATEGORY_PLATES:
        plate = Plate(f"category-{slug}", "coat", slug != "men", 1200, 1500, palette_index)
        # Reuse the source plate's garment so each card shows a different shape.
        garment = {"men": "jacket", "women": "coat", "accessories": "sweater"}[slug]
        plate = Plate(plate.name, garment, slug != "men", 1200, 1500, palette_index)
        image = render_plate(plate)
        out = demo_dir / f"{slug}.png"
        image.convert("P", palette=Image.Palette.ADAPTIVE, colors=128).save(
            out, "PNG", optimize=True
        )
        print(f"  {out.name:20} {plate.width}x{plate.height}  {out.stat().st_size // 1024} KB")


# ------------------------------------------------------- wide hero banners
# Full-bleed slides for the homepage carousel. Composition rules differ from the
# portrait plates: figures sit on the RIGHT third and the left is deliberately
# emptied and darkened, because the headline is overlaid there. A centred figure
# would fight the type.
WIDE_W, WIDE_H = 2400, 1100


@dataclass(frozen=True)
class Banner:
    name: str
    garments: tuple[str, ...]
    feminine: tuple[bool, ...]
    palette_index: int


BANNERS: list[Banner] = [
    Banner("hero-wide-01", ("coat", "jacket", "jacket"), (True, True, False), 3),
    Banner("hero-wide-02", ("jeans", "jacket", "jeans"), (False, True, True), 0),
    Banner("hero-wide-03", ("kurta", "abaya", "kurta"), (True, True, False), 1),
    Banner("hero-wide-04", ("sweater", "coat", "hoodie"), (True, False, False), 4),
]


def render_banner(banner: Banner) -> Image.Image:
    palette = PALETTES[banner.palette_index % len(PALETTES)]
    width, height = WIDE_W * 2, WIDE_H * 2  # lighter supersample; these are large

    canvas = _gradient((width, height), palette.bg_top, palette.bg_bottom).convert("RGBA")

    # Colour field on the right, behind the group.
    band = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(band).rectangle([width * 0.46, 0, width, height], fill=(*palette.accent, 34))
    canvas.alpha_composite(band.filter(ImageFilter.GaussianBlur(width // 160)))

    # Floor.
    horizon = height * 0.86
    floor = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(floor).rectangle(
        [0, horizon, width, height], fill=(*_lerp(palette.bg_bottom, INK, 0.12), 210)
    )
    canvas.alpha_composite(floor.filter(ImageFilter.GaussianBlur(width // 300)))

    # Three figures at staggered scale and depth — a group reads as a campaign,
    # a lone figure reads as a product shot.
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    spots = [(0.62, 0.88), (0.76, 0.96), (0.89, 0.82)]
    for index, (garment, feminine) in enumerate(zip(banner.garments, banner.feminine)):
        x_frac, scale = spots[index]
        fig_h = horizon * scale
        _draw_figure(
            draw,
            width * x_frac,
            horizon - fig_h,
            fig_h,
            palette,
            garment=garment,
            feminine=feminine,
            pose=index,
        )
    canvas.alpha_composite(layer)

    # Left-side scrim. The headline sits here, so it has to be genuinely dark —
    # a light wash would leave white type unreadable on a pale ground.
    scrim = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    scrim_draw = ImageDraw.Draw(scrim)
    for i in range(140):
        t = i / 139
        x = int(width * 0.72 * t)
        scrim_draw.rectangle([x, 0, x + width // 120, height], fill=(10, 9, 8, int(232 * (1 - t) ** 1.5)))
    canvas.alpha_composite(scrim.filter(ImageFilter.GaussianBlur(width // 90)))

    out = canvas.convert("RGB").resize((WIDE_W, WIDE_H), Image.Resampling.LANCZOS)
    return _grain(_vignette(out, 0.18))


def render_banners() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for banner in BANNERS:
        image = render_banner(banner)
        path = OUT_DIR / f"{banner.name}.jpg"
        image.save(path, "JPEG", quality=86, optimize=True, progressive=True)
        print(f"  {path.name:22} {WIDE_W}x{WIDE_H}  {path.stat().st_size // 1024} KB")
