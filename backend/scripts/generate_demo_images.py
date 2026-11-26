"""Generate placeholder catalogue imagery for local development.

Run once to produce the static demo assets under `frontend/public/demo/`; the
generated PNGs are then committed and served by Next.js like any other image.

This is a developer tool, not part of the application. Pillow is therefore not
listed in requirements.txt — install it only when regenerating assets:

    pip install pillow
    python scripts/generate_demo_images.py

Every image is drawn from scratch here. Nothing is downloaded, and no third
party photography is used.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.seeds.catalog_data import BRANDS, CATEGORIES, PRODUCTS  # noqa: E402

OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "demo"

INK = (17, 17, 17)
GOLD = (195, 154, 81)
PAPER = (250, 248, 244)

# Warm, muted grounds so the grid reads as one editorial set rather than a
# rainbow of unrelated swatches.
TONES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "Indigo": ((38, 47, 71), (28, 35, 55)),
    "Mid Blue": ((74, 96, 126), (58, 76, 102)),
    "Light Wash": ((176, 190, 208), (156, 172, 194)),
    "Washed Blue": ((108, 132, 158), (88, 110, 136)),
    "Ecru": ((233, 224, 208), (219, 207, 187)),
    "Slate": ((104, 112, 118), (86, 94, 100)),
    "Charcoal": ((62, 62, 64), (48, 48, 50)),
    "Olive": ((104, 108, 78), (86, 90, 64)),
    "Black": ((38, 38, 38), (26, 26, 26)),
    "Sand": ((222, 205, 180), (206, 187, 160)),
    "Forest": ((48, 74, 62), (36, 58, 48)),
    "Natural": ((226, 216, 198), (211, 199, 178)),
    "Stone": ((196, 190, 180), (178, 171, 160)),
    "Brown": ((122, 88, 60), (100, 71, 47)),
    "Oat": ((225, 214, 194), (209, 196, 174)),
}
FALLBACK_TONE = ((214, 206, 194), (196, 187, 173))


def _font(names: tuple[str, ...], size: int) -> ImageFont.FreeTypeFont:
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def serif(size: int) -> ImageFont.FreeTypeFont:
    return _font(("georgia.ttf", "times.ttf", "DejaVuSerif.ttf"), size)


def _tone(color: str | None) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    return TONES.get(color or "", FALLBACK_TONE)


def _vertical_gradient(
    size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]
) -> Image.Image:
    width, height = size
    base = Image.new("RGB", (1, height))
    pixels = base.load()
    for y in range(height):
        ratio = y / max(height - 1, 1)
        pixels[0, y] = tuple(
            round(top[channel] + (bottom[channel] - top[channel]) * ratio) for channel in range(3)
        )
    return base.resize(size, Image.Resampling.BILINEAR)


def _luminance(color: tuple[int, int, int]) -> float:
    return (0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]) / 255


# These stand in for photography, so they carry no baked-in captions. The
# interface already renders the product name, brand, colour and category, and
# repeating that text inside the image would duplicate it on every card and get
# clipped by the object-cover crop at different aspect ratios.
def product_image(color: str | None, index: int) -> Image.Image:
    """A 3:4 tonal plate. Portrait suits garments and prevents layout shift."""
    width, height = 900, 1200
    top, bottom = _tone(color)
    canvas = _vertical_gradient((width, height), top, bottom)
    draw = ImageDraw.Draw(canvas, "RGBA")

    on_dark = _luminance(top) < 0.5
    veil = (255, 255, 255, 30) if on_dark else (255, 255, 255, 70)
    shade = (0, 0, 0, 26)

    # Rotating geometry gives each image of a product a distinct composition
    # while keeping the whole set visually related.
    variant = index % 3
    if variant == 0:
        draw.ellipse([width * 0.14, height * 0.16, width * 0.86, height * 0.70], fill=veil)
        draw.ellipse([width * 0.36, height * 0.58, width * 1.06, height * 1.16], fill=shade)
    elif variant == 1:
        draw.pieslice(
            [width * 0.02, height * 0.10, width * 0.98, height * 1.02], 180, 360, fill=veil
        )
        draw.rectangle([0, round(height * 0.80), width, height], fill=shade)
    else:
        draw.rounded_rectangle(
            [width * 0.22, height * 0.12, width * 0.78, height * 0.74], radius=300, fill=veil
        )
        draw.ellipse([-width * 0.20, height * 0.62, width * 0.44, height * 1.18], fill=shade)

    # Discreet corner monogram, the only mark on the image.
    draw.text(
        (round(width * 0.86), round(height * 0.045)),
        "RG",
        font=serif(58),
        fill=(*GOLD, 210),
    )
    return canvas


# Each department gets its own dark tone so the three tiles read as a designed
# set rather than three identical black rectangles.
CATEGORY_TONES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "men": ((34, 38, 50), (18, 20, 27)),
    "women": ((56, 38, 42), (28, 19, 22)),
    "accessories": ((44, 44, 33), (22, 22, 17)),
}


def category_image(slug: str) -> Image.Image:
    """Tall 4:5 plate, so both the portrait hero and the 4:3 tile crop cleanly."""
    width, height = 1200, 1500
    top, bottom = CATEGORY_TONES.get(slug, ((32, 31, 29), (17, 17, 16)))
    canvas = _vertical_gradient((width, height), top, bottom)
    draw = ImageDraw.Draw(canvas, "RGBA")

    # Large soft arc bleeding off two edges — reads as lighting, not a shape.
    draw.ellipse(
        [width * 0.26, -height * 0.22, width * 1.30, height * 0.72], fill=(255, 255, 255, 20)
    )
    draw.ellipse(
        [-width * 0.34, height * 0.54, width * 0.62, height * 1.34], fill=(0, 0, 0, 34)
    )
    draw.text(
        (round(width * 0.84), round(height * 0.035)), "RG", font=serif(64), fill=(*GOLD, 195)
    )
    return canvas


def brand_logo(name: str) -> Image.Image:
    """Monogram plate. The interface prints the brand name, so the mark does not."""
    size = 520
    canvas = Image.new("RGB", (size, size), PAPER)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, size - 1, size - 1], outline=(226, 220, 210), width=3)

    initials = "".join(part[0] for part in name.replace("&", " ").split() if part)[:2].upper()
    font = serif(210)
    box = draw.textbbox((0, 0), initials, font=font)
    draw.text(
        ((size - (box[2] - box[0])) / 2 - box[0], (size * 0.40) - (box[3] - box[1]) / 2 - box[1]),
        initials,
        font=font,
        fill=INK,
    )
    draw.rectangle([size * 0.42, size * 0.66, size * 0.58, size * 0.66 + 3], fill=GOLD)
    return canvas


def main() -> None:
    products_dir = OUTPUT_ROOT / "products"
    categories_dir = OUTPUT_ROOT / "categories"
    brands_dir = OUTPUT_ROOT / "brands"
    for directory in (products_dir, categories_dir, brands_dir):
        directory.mkdir(parents=True, exist_ok=True)

    written = 0
    for product in PRODUCTS:
        for index in range(product.image_count):
            product_image(product.color, index).save(
                products_dir / f"{product.slug}-{index + 1}.png", optimize=True
            )
            written += 1

    for category in CATEGORIES:
        category_image(category.slug).save(categories_dir / f"{category.slug}.png", optimize=True)
        written += 1

    for brand in BRANDS:
        brand_logo(brand.name).save(brands_dir / f"{brand.slug}.png", optimize=True)
        written += 1

    print(f"Wrote {written} demo images to {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
