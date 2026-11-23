"""Probe whether Gemini can replace PatchCore as the image stage.

This is an evaluation harness, not part of the app. It sends a photo to Gemini,
asks for a verdict plus normalized defect boxes, annotates the photo, and prints
what the rules would make of the answer. Run it against your own photos and
decide whether you like the behaviour.

Setup (from ``backend/``)::

    export GEMINI_API_KEY=...
    # optional, defaults to gemini-2.5-flash
    export GEMINI_MODEL=gemini-2.5-flash

One image::

    uv run python -m scripts.gemini_probe \
        --image ../samples/images/bottle_contamination_000.png

A whole folder, three runs each, to see how stable the answers are::

    uv run python -m scripts.gemini_probe \
        --dir ../samples/images --repeat 3

Side by side with the real detector::

    uv run python -m scripts.gemini_probe \
        --image ../samples/images/bottle_good_000.png \
        --compare results/Patchcore/MVTecAD/bottle/v1/weights/lightning/model.ckpt

Annotated photos and a JSONL log are written to ``data/outputs/gemini_probe``.
"""

from __future__ import annotations

import argparse
import io
import json
import time
from pathlib import Path
from typing import Any, Literal

import numpy as np
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, Field

from app.core.categories import CategoryConfig, load_category_config
from app.core.config import get_settings
from app.core.persona import PersonaConfig, load_persona

DEFAULT_MODEL = "gemini-2.5-pro"
DEFAULT_OUT_DIR = Path("data/outputs/gemini_probe")
CATEGORY_DIR = Path(__file__).resolve().parents[1] / "config" / "categories"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
BOX_SCALE = 1000
IMAGE_MAX_SIDE = 1024
JPEG_QUALITY = 92
JSON_MIME_TYPE = "application/json"
JPEG_MIME_TYPE = "image/jpeg"
GRID_SIDE = 3
GRID_REGIONS = (
    "upper left",
    "upper center",
    "upper right",
    "middle left",
    "center",
    "middle right",
    "lower left",
    "lower center",
    "lower right",
)
TONE_COLORS = {
    "pass": (22, 163, 74),
    "defect": (220, 38, 38),
    "uncertain": (217, 119, 6),
}
FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


class GeminiBox(BaseModel):
    """One defect region as 0-1000 normalized corners."""

    ymin: int = Field(ge=0, le=BOX_SCALE)
    xmin: int = Field(ge=0, le=BOX_SCALE)
    ymax: int = Field(ge=0, le=BOX_SCALE)
    xmax: int = Field(ge=0, le=BOX_SCALE)
    label: str


class GeminiVerdict(BaseModel):
    """What Gemini says about one photo, in the shape the rules need."""

    part_present: bool
    view_ok: bool
    category: str
    verdict: Literal["pass", "defect", "uncertain"]
    defect_type: str | None
    severity: Literal["none", "low", "medium", "high"]
    confidence: float = Field(ge=0, le=1)
    boxes: list[GeminiBox]
    reasoning: str


def build_prompt(category: CategoryConfig) -> str:
    """Build the inspection prompt for one category."""
    defect_types = ", ".join(category.defect_types)
    return f"""You are the vision stage of an automated factory QC station.
Inspect the attached photo of a single manufactured part.

The expected part is a "{category.display_name}" ({category.description}).
Allowed defect types for this category: {defect_types}.

Rules:
- Set part_present to false if no such part is visible.
- Set view_ok to false if the part is too blurry, too dark, cut off,
  or shown at an angle that hides the surface being inspected.
- verdict is "pass" when the part is undamaged, "defect" when you can see
  damage, and "uncertain" when the photo does not let you decide.
- Report every defect you can see in boxes. Boxes use 0-1000 normalized
  coordinates measured from the top-left corner, as
  ymin, xmin, ymax, xmax. Tight boxes only, one per defect.
  Return an empty list for a pass.
- defect_type must be one of the allowed types above, or null for a pass.
- severity is "none" for a pass, otherwise "low", "medium" or "high"
  judged by how much of the part is affected and how deep it looks.
- confidence is your own 0-1 certainty in the verdict. It is not calibrated;
  do not inflate it.
- reasoning is one short sentence, no markdown.
"""


def ask_gemini(
    client: genai.Client,
    model: str,
    photo: Image.Image,
    prompt: str,
    temperature: float,
) -> tuple[GeminiVerdict, float, dict[str, int | None]]:
    """Send one photo and return the parsed verdict, the latency and token counts."""
    started = time.perf_counter()
    response = client.models.generate_content(
        model=model,
        contents=[types.Part(text=prompt), _image_part(photo)],
        config=types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type=JSON_MIME_TYPE,
            response_schema=GeminiVerdict,
        ),
    )
    elapsed_ms = (time.perf_counter() - started) * 1000
    if not response.text:
        raise RuntimeError("Gemini returned no text.")
    usage = response.usage_metadata
    tokens = {
        "prompt": getattr(usage, "prompt_token_count", None),
        "output": getattr(usage, "candidates_token_count", None),
    }
    return GeminiVerdict.model_validate_json(response.text), elapsed_ms, tokens


def _image_part(photo: Image.Image) -> types.Part:
    """Downscale the photo and encode it as a JPEG part."""
    prepared = photo.copy()
    prepared.thumbnail((IMAGE_MAX_SIDE, IMAGE_MAX_SIDE), Image.Resampling.LANCZOS)
    buffer = _jpeg_bytes(prepared)
    return types.Part.from_bytes(data=buffer, mime_type=JPEG_MIME_TYPE)


def _jpeg_bytes(photo: Image.Image) -> bytes:
    """Encode a PIL image as JPEG bytes."""
    buffer = io.BytesIO()
    photo.convert("RGB").save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return buffer.getvalue()


def usable_boxes(verdict: GeminiVerdict) -> list[GeminiBox]:
    """Drop degenerate or inverted boxes before drawing or measuring them."""
    return [box for box in verdict.boxes if box.ymax > box.ymin and box.xmax > box.xmin]


def box_mask(boxes: list[GeminiBox], size: tuple[int, int]) -> np.ndarray:
    """Rasterize the boxes into a boolean mask so the rules can measure them."""
    width, height = size
    mask = np.zeros((height, width), dtype=bool)
    for box in boxes:
        pixel = pixel_box(box, size)
        if pixel is None:
            continue
        left, top, right, bottom = pixel
        mask[top : bottom + 1, left : right + 1] = True
    return mask


def pixel_box(box: GeminiBox, size: tuple[int, int]) -> tuple[int, int, int, int] | None:
    """Convert one normalized box to clamped pixel corners, or None if empty."""
    width, height = size
    left = _clamp(int(box.xmin / BOX_SCALE * width), width)
    top = _clamp(int(box.ymin / BOX_SCALE * height), height)
    right = _clamp(int(box.xmax / BOX_SCALE * width), width)
    bottom = _clamp(int(box.ymax / BOX_SCALE * height), height)
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _clamp(value: int, upper: int) -> int:
    """Keep a pixel coordinate inside the image."""
    return max(0, min(upper - 1, value))


def severity_from_ratio(ratio: float, category: CategoryConfig) -> str:
    """Map the box area ratio to a severity with the category's own bands."""
    bands = category.severity_bands
    if ratio <= bands["low_max"]:
        return "low"
    if ratio <= bands["medium_max"]:
        return "medium"
    return "high"


def region_from_mask(mask: np.ndarray) -> str | None:
    """Return the 3x3 grid cell of the flagged centroid, as the rules do."""
    if mask.ndim != 2 or not np.any(mask):
        return None
    rows, columns = np.nonzero(mask)
    height, width = mask.shape
    center_x = (float(columns.mean()) + 0.5) / width
    center_y = (float(rows.mean()) + 0.5) / height
    column_index = min(int(center_x * GRID_SIDE), GRID_SIDE - 1)
    row_index = min(int(center_y * GRID_SIDE), GRID_SIDE - 1)
    return GRID_REGIONS[row_index * GRID_SIDE + column_index]


def annotate(photo: Image.Image, verdict: GeminiVerdict, caption: str, out_path: Path) -> Path:
    """Draw the boxes and a caption band on a copy of the photo and save it."""
    canvas = photo.convert("RGBA")
    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    color = TONE_COLORS.get(verdict.verdict, TONE_COLORS["uncertain"])
    bar_height = 38
    draw.rectangle([0, 0, canvas.width, bar_height], fill=(*color, 235))
    draw.text((10, 10), caption, font=_font(16), fill=(255, 255, 255, 255))
    for index, box in enumerate(usable_boxes(verdict), start=1):
        pixel = pixel_box(box, canvas.size)
        if pixel is None:
            continue
        left, top, right, bottom = pixel
        draw.rectangle([left, top, right, bottom], outline=(*color, 255), width=3)
        label = f"{index}. {box.label}"
        label_width = draw.textlength(label, font=_font(14))
        label_top = max(bar_height + 2, top - 20)
        draw.rectangle(
            [left, label_top, left + label_width + 8, label_top + 18],
            fill=(*color, 220),
        )
        draw.text((left + 4, label_top + 2), label, font=_font(14), fill=(255, 255, 255, 255))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.alpha_composite(canvas, layer).convert("RGB").save(out_path)
    return out_path


def _font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Load a readable font, falling back to Pillow's built-in bitmap font."""
    for candidate in FONT_CANDIDATES:
        path = Path(candidate)
        if path.is_file():
            return ImageFont.truetype(str(path), size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def infer_category(path: Path) -> str:
    """Guess the category from the file name, e.g. bottle_good_000.png."""
    ids = _known_category_ids()
    for category_id in sorted(ids, key=len, reverse=True):
        if path.name.lower().startswith(category_id):
            return category_id
    raise ValueError(f"Cannot infer the category of {path.name}; pass --category.")


def _known_category_ids() -> list[str]:
    """Read the ids from the category config files without loading any model."""
    ids: list[str] = []
    for config_path in sorted(CATEGORY_DIR.glob("*.json")):
        raw = json.loads(config_path.read_text())
        category_id = raw.get("id")
        if isinstance(category_id, str):
            ids.append(category_id)
    return ids


def run_gemini(
    client: genai.Client,
    model: str,
    photo: Image.Image,
    category: CategoryConfig,
    temperature: float,
    repeat: int,
) -> dict[str, Any]:
    """Ask Gemini ``repeat`` times and summarise the answers."""
    prompt = build_prompt(category)
    verdicts: list[GeminiVerdict] = []
    latencies: list[float] = []
    tokens: dict[str, int | None] = {"prompt": None, "output": None}
    for _ in range(max(1, repeat)):
        verdict, elapsed_ms, usage = ask_gemini(client, model, photo, prompt, temperature)
        verdicts.append(verdict)
        latencies.append(elapsed_ms)
        tokens = usage
    first = verdicts[0]
    boxes = usable_boxes(first)
    mask = box_mask(boxes, photo.size)
    ratio = float(mask.mean()) if mask.size else 0.0
    return {
        "verdicts": [verdict.verdict for verdict in verdicts],
        "confidences": [round(verdict.confidence, 3) for verdict in verdicts],
        "box_counts": [len(usable_boxes(verdict)) for verdict in verdicts],
        "verdict": first.verdict,
        "defect_type": first.defect_type,
        "severity": first.severity,
        "severity_from_boxes": None
        if first.verdict == "pass"
        else severity_from_ratio(ratio, category),
        "confidence": first.confidence,
        "region": region_from_mask(mask),
        "area_ratio": round(ratio, 4),
        "boxes": [box.model_dump() for box in boxes],
        "part_present": first.part_present,
        "view_ok": first.view_ok,
        "reasoning": first.reasoning,
        "latency_ms": [round(value, 1) for value in latencies],
        "tokens": tokens,
    }


def run_patchcore(
    checkpoint: Path,
    photo: Image.Image,
    persona: PersonaConfig,
) -> dict[str, Any]:
    """Score the same photo with the real detector and the real rules."""
    from app.models.factory import create_detector
    from app.services.rules import assess

    detector = create_detector(checkpoint, "auto")
    started = time.perf_counter()
    detection = detector.detect(photo)
    elapsed_ms = (time.perf_counter() - started) * 1000
    assessment = assess(detection.score, detection.mask, persona)
    return {
        "verdict": assessment.verdict.value,
        "severity": assessment.severity.value,
        "confidence": round(assessment.confidence, 3),
        "region": assessment.location.region if assessment.location else None,
        "area_ratio": round(assessment.area_ratio, 4),
        "needs_review": assessment.needs_review,
        "action": assessment.action.value,
        "score": round(detection.score, 4),
        "latency_ms": round(elapsed_ms, 1),
    }


def print_report(
    image_path: Path, category_id: str, gemini: dict[str, Any], patchcore: dict | None
) -> None:
    """Print one compact block per image."""
    verdicts = ",".join(gemini["verdicts"])
    confidences = ",".join(str(value) for value in gemini["confidences"])
    latencies = ",".join(str(value) for value in gemini["latency_ms"])
    print(f"\n=== {image_path.name}  [{category_id}]")
    print(f"  gemini    verdict={verdicts}")
    print(f"            type={gemini['defect_type']}  severity={gemini['severity']}")
    print(
        f"            boxes={gemini['box_counts']}  area={gemini['area_ratio']:.2%}"
        f"  region={gemini['region']}"
    )
    print(f"            confidence={confidences}  latency_ms={latencies}")
    if gemini["tokens"]["prompt"] is not None:
        print(f"            tokens={gemini['tokens']['prompt']}+{gemini['tokens']['output']}")
    print(f"            part_present={gemini['part_present']}  view_ok={gemini['view_ok']}")
    print(f"            why: {gemini['reasoning']}")
    if patchcore is not None:
        print(
            f"  patchcore verdict={patchcore['verdict']}  severity={patchcore['severity']}"
            f"  score={patchcore['score']}  area={patchcore['area_ratio']:.2%}"
        )
        print(
            f"            region={patchcore['region']}  action={patchcore['action']}"
            f"  review={patchcore['needs_review']}  latency_ms={patchcore['latency_ms']}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path, help="one photo to inspect")
    source.add_argument("--dir", type=Path, help="a folder of photos to inspect")
    parser.add_argument("--category", help="category id; inferred from the file name if omitted")
    parser.add_argument("--api-key", help="Gemini API key; defaults to GEMINI_API_KEY")
    parser.add_argument("--model", help="Gemini model; defaults to GEMINI_MODEL or a fallback")
    parser.add_argument("--persona", default="factory_qc_operator", help="persona config name")
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="0.0 for repeatable answers, 1.0 for the API default",
    )
    parser.add_argument("--repeat", type=int, default=1, help="runs per photo")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--no-annotate", action="store_true", help="skip the overlay images")
    parser.add_argument(
        "--compare",
        type=Path,
        help="PatchCore checkpoint to score the same photos with the real detector",
    )
    return parser.parse_args(argv)


def collect_images(args: argparse.Namespace) -> list[Path]:
    """Return the photos named by --image or found in --dir."""
    if args.image is not None:
        if not args.image.is_file():
            raise SystemExit(f"Image not found: {args.image}")
        return [args.image]
    if not args.dir.is_dir():
        raise SystemExit(f"Directory not found: {args.dir}")
    images = sorted(path for path in args.dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)
    if not images:
        raise SystemExit(f"No images found in {args.dir}")
    return images


def main(argv: list[str] | None = None) -> None:
    """Run the probe over the requested photos."""
    args = parse_args(argv)
    settings = get_settings()
    api_key = args.api_key
    if not api_key and settings.gemini_api_key is not None:
        api_key = settings.gemini_api_key.get_secret_value()
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY (or pass --api-key) before running this probe.")
    model = args.model or settings.gemini_model or DEFAULT_MODEL
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1beta"))
    persona = load_persona(args.persona)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    log_path = args.out_dir / "results.jsonl"
    print(f"model={model}  temperature={args.temperature}  repeat={args.repeat}")

    with log_path.open("a", encoding="utf-8") as log:
        for image_path in collect_images(args):
            category_id = args.category or infer_category(image_path)
            category = load_category_config(category_id)
            photo = Image.open(image_path).convert("RGB")
            gemini = run_gemini(client, model, photo, category, args.temperature, args.repeat)
            patchcore = None
            if args.compare is not None:
                patchcore = run_patchcore(args.compare, photo, persona.for_category(category))
            caption = (
                f"Gemini: {gemini['verdict']} | {category_id} | "
                f"conf {gemini['confidence']:.2f} | {gemini['box_counts'][0]} box(es)"
            )
            if not args.no_annotate:
                out_path = args.out_dir / f"{image_path.stem}_gemini.png"
                annotate(photo, _as_verdict(gemini), caption, out_path)
                print(f"  annotated -> {out_path}")
            print_report(image_path, category_id, gemini, patchcore)
            log.write(
                json.dumps(
                    {
                        "image": str(image_path),
                        "category": category_id,
                        "model": model,
                        "gemini": gemini,
                        "patchcore": patchcore,
                    }
                )
                + "\n"
            )

    print(f"\nLog appended to {log_path}")


def _as_verdict(gemini: dict[str, Any]) -> GeminiVerdict:
    """Rebuild a verdict object for drawing from the summarised record."""
    return GeminiVerdict(
        part_present=bool(gemini["part_present"]),
        view_ok=bool(gemini["view_ok"]),
        category="",
        verdict=gemini["verdict"],
        defect_type=gemini["defect_type"],
        severity=gemini["severity"],
        confidence=float(gemini["confidence"]),
        boxes=[GeminiBox(**box) for box in gemini["boxes"]],
        reasoning=str(gemini["reasoning"]),
    )


if __name__ == "__main__":
    main()
