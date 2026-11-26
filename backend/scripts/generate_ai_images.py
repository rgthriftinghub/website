"""Generate storefront imagery with the OpenAI image API.

Replaces the hand-drawn placeholder plates with real photographic imagery.

**This costs money.** Every run bills the key in `.env`, so nothing happens without
an explicit `--kind`, and `--dry-run` prints the plan and exits. Existing files are
skipped unless `--force` is passed, so a re-run does not silently re-bill for
images you already have.

The key is read from the environment or `.env` and is never logged, printed, or
written into a filename.

Usage:
    python scripts/generate_ai_images.py --kind hero            # 4 wide banners
    python scripts/generate_ai_images.py --kind plates          # 14 portrait plates
    python scripts/generate_ai_images.py --kind hero --dry-run
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from io import BytesIO

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "frontend" / "public" / "editorial"
API_URL = "https://api.openai.com/v1/images/generations"

# Tried in order; the first the account accepts is used. Newer models produce
# better fabric and skin rendering, but availability varies by account.
MODELS = ("gpt-image-2.5-sunburst", "gpt-image-2", "gpt-image-1.5", "gpt-image-1")

# Landscape is the widest the API offers, so wide banners are generated at this
# size and then cropped to the hero band.
SIZE_LANDSCAPE = "2560x1440"
SIZE_PORTRAIT = "1152x2048"

# Final on-disk dimensions.
HERO_W, HERO_H = 2560, 1440
PLATE_W, PLATE_H = 1152, 1440

# Appended to every prompt. Keeps output usable as a backdrop for overlaid type
# and keeps third-party marks out of the frame.
COMMON = (
    "Photorealistic high-resolution editorial fashion photograph, medium-format sharpness, "
    "crisp fine fabric detail and visible texture. RICH SATURATED COLOUR: deep indigo, "
    "emerald green, mustard yellow, burnt orange, terracotta, ruby red and cobalt blue in "
    "the clothing. Vivid and lively, not muted, not beige, not monochrome. Bright clean "
    "even lighting against a complementary coloured backdrop. "
    "No text, no lettering, no watermarks, no logos, no brand marks."
)

HERO_SUFFIX = (
    " Wide 16:9 cinematic composition. All subjects stand together in the RIGHT HALF of the "
    "frame, entirely inside it with a clear margin from the right edge — nobody clipped or "
    "cut off by any frame edge. The LEFT THIRD is empty backdrop for overlaid headline text. "
    "Full figures visible from head to below the knee, with generous space above the heads."
)

@dataclass(frozen=True)
class Job:
    filename: str
    prompt: str
    portrait: bool


HERO_JOBS: list[Job] = [
    Job(
        "hero-wide-01.jpg",
        "Three South Asian models standing together in a bright minimal studio, wearing "
        "second-hand tailored wool overcoats and structured blazers in charcoal, camel and "
        "deep navy. Relaxed confident posture." + HERO_SUFFIX,
        False,
    ),
    Job(
        "hero-wide-02.jpg",
        "Two South Asian women in a sunlit minimal studio wearing vintage straight-leg and "
        "high-rise blue denim jeans with tucked plain white tees and leather belts. Casual "
        "editorial stance, denim texture clearly visible." + HERO_SUFFIX,
        False,
    ),
    Job(
        "hero-wide-03.jpg",
        "MENSWEAR ONLY. Three adult South Asian MEN, all male, no women anywhere in the "
        "frame. They wear a menswear edit: an emerald green field jacket, a cobalt blue "
        "oxford shirt with mustard chinos, and a burnt orange crewneck sweatshirt. Western "
        "casual clothing only — absolutely no kurtas, no abayas, no traditional eastern "
        "wear. Easy confident posture." + HERO_SUFFIX,
        False,
    ),
    Job(
        "hero-wide-04.jpg",
        "Two South Asian models in a cool minimal studio wearing heavy winter clothing: a "
        "thick wool tweed overcoat and a chunky cream cable-knit sweater with a wool scarf. "
        "Textured fabric, wintry muted light." + HERO_SUFFIX,
        False,
    ),
    Job(
        "hero-wide-05.jpg",
        "Two young South Asian models in a minimal studio wearing oversized baggy wide-leg "
        "jeans with boxy cropped tops in electric blue and orange, and a loose denim jacket, "
        "streetwear styling, relaxed slouchy silhouette." + HERO_SUFFIX,
        False,
    ),
]


PLATE_SPECS: list[tuple[str, str]] = [
    ("women-denim-01", "a South Asian woman wearing straight-leg indigo jeans and a plain white tee"),
    ("women-baggy-01", "a South Asian woman wearing oversized baggy wide-leg jeans and a boxy top"),
    ("women-coat-01", "a South Asian woman wearing a long tailored wool overcoat in camel"),
    ("women-jacket-01", "a South Asian woman wearing a cropped vintage denim jacket"),
    ("women-sweater-01", "a South Asian woman wearing an oversized cream cable-knit sweater"),
    ("women-dress-01", "a South Asian woman wearing a simple midi dress in deep burgundy"),
    ("women-skirt-01", "a South Asian woman wearing a pleated midi skirt in olive"),
    ("men-denim-01", "a South Asian man wearing vintage straight-leg denim jeans and a plain shirt"),
    ("men-baggy-01", "a South Asian man wearing oversized baggy wide-leg jeans and a loose tee"),
    ("men-coat-01", "a South Asian man wearing a charcoal wool overcoat"),
    ("men-jacket-01", "a South Asian man wearing a worn leather jacket"),
    ("men-shirt-01", "a South Asian man wearing a crisp white linen shirt"),
    ("men-hoodie-01", "a South Asian man wearing a plain grey hooded sweatshirt"),
]


PLATE_JOBS: list[Job] = [
    Job(
        f"{name}.jpg",
        f"Studio fashion photograph of {desc}, second-hand clothing in excellent condition. "
        "Single subject centred against a boldly coloured seamless backdrop, framed from "
        "head to below the knee, entirely inside the frame with space above the head.",
        True,
    )
    for name, desc in PLATE_SPECS
]


def load_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if key:
        return key
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip().startswith("OPENAI_API_KEY="):
                return line.partition("=")[2].strip().strip('"').strip("'")
    sys.exit("OPENAI_API_KEY not found in the environment or .env")


def request_image(key: str, prompt: str, size: str, model: str, *, cheap: bool = False) -> bytes:
    """One generation call. Returns raw image bytes."""
    payload = json.dumps(
        {
            "model": model,
            "prompt": f"{prompt} {COMMON}",
            "size": size,
            "quality": "medium" if cheap else "high",
            "n": 1,
        }
    ).encode()
    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as response:
        body = json.load(response)

    entry = body["data"][0]
    if entry.get("b64_json"):
        return base64.b64decode(entry["b64_json"])
    # Some models return a URL instead of inline base64.
    with urllib.request.urlopen(entry["url"], timeout=180) as image_response:
        return image_response.read()


def pick_model(key: str) -> str:
    """Find the first model this account can actually call.

    Probing with a real (smallest) generation rather than trusting the model list,
    because being listed does not guarantee the account may use it.
    """
    for model in MODELS:
        try:
            request_image(key, "A plain grey seamless studio backdrop.", "1024x1024", model, cheap=True)
            print(f"  using model: {model}")
            return model
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode()[:140]
            print(f"  {model}: HTTP {exc.code} {detail}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {model}: {type(exc).__name__} {str(exc)[:110]}")
    sys.exit("No usable image model for this account.")


def fit(raw: bytes, width: int, height: int) -> Image.Image:
    """Centre-crop to the target aspect, then resize.

    The API's landscape output is 3:2 while the hero band is roughly 2.2:1, so the
    crop takes a horizontal slice from the middle — where the subjects are — rather
    than squashing the frame.
    """
    image = Image.open(BytesIO(raw)).convert("RGB")
    target = width / height
    source = image.width / image.height
    if source > target:
        new_w = int(image.height * target)
        left = (image.width - new_w) // 2
        image = image.crop((left, 0, left + new_w, image.height))
    else:
        new_h = int(image.width / target)
        # Take almost everything off the bottom: a hero may lose feet, never faces.
        top = int((image.height - new_h) * 0.10)
        image = image.crop((0, top, image.width, top + new_h))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def run(jobs: list[Job], *, force: bool, dry_run: bool) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pending = [job for job in jobs if force or not (OUT_DIR / job.filename).exists()]
    skipped = len(jobs) - len(pending)

    print(f"  {len(pending)} to generate, {skipped} already present (use --force to redo)")
    if dry_run:
        for job in pending:
            print(f"    would generate {job.filename}")
        return
    if not pending:
        return

    key = load_key()
    model = pick_model(key)

    for index, job in enumerate(pending, start=1):
        size = SIZE_PORTRAIT if job.portrait else SIZE_LANDSCAPE
        width, height = (PLATE_W, PLATE_H) if job.portrait else (HERO_W, HERO_H)
        for attempt in (1, 2, 3):
            try:
                raw = request_image(key, job.prompt, size, model)
                out = OUT_DIR / job.filename
                fit(raw, width, height).save(
                    out, "JPEG", quality=92, optimize=True, progressive=True
                )
                print(
                    f"  [{index}/{len(pending)}] {job.filename:22} "
                    f"{width}x{height}  {out.stat().st_size // 1024} KB"
                )
                break
            except Exception as exc:  # noqa: BLE001
                # Rate limits and transient 5xx are common on image endpoints.
                wait = 6 * attempt
                print(f"    attempt {attempt} failed ({str(exc)[:90]}); retrying in {wait}s")
                if attempt == 3:
                    print(f"  [{index}/{len(pending)}] {job.filename} GAVE UP")
                else:
                    time.sleep(wait)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("hero", "plates", "all"), required=True)
    parser.add_argument("--force", action="store_true", help="regenerate existing files")
    parser.add_argument("--dry-run", action="store_true", help="show the plan, bill nothing")
    args = parser.parse_args()

    jobs = {
        "hero": HERO_JOBS,
        "plates": PLATE_JOBS,
        "all": HERO_JOBS + PLATE_JOBS,
    }[args.kind]
    run(jobs, force=args.force, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
