"""Render the annotated overlay and the history thumbnail for one photo."""

import logging

import numpy as np
from PIL import Image, ImageDraw

from app.schemas import DefectLocation

logger = logging.getLogger(__name__)

OVERLAY_TINT = (255, 0, 0)
OVERLAY_OPACITY = 0.5
BOX_WIDTH_PIXELS = 2
MASK_ON_VALUE = 255
MASK_RESAMPLING = Image.Resampling.NEAREST
THUMBNAIL_RESAMPLING = Image.Resampling.LANCZOS
THUMBNAIL_MODE = "RGB"


def render_overlay(
    photo: Image.Image, detection_mask: np.ndarray, location: DefectLocation | None
) -> Image.Image:
    """Return the photo with flagged mask pixels tinted red and the defect boxed.

    Only the binary mask is tinted, so a good item keeps its original pixels.
    A mask that is not two-dimensional, or flags nothing, is left untouched.

    Args:
        photo: The original RGB photo.
        detection_mask: Boolean mask of the pixels the detector flagged.
        location: The flagged region and normalized box, or None.

    Returns:
        A new RGB image the same size as the photo.
    """
    if detection_mask.ndim != 2 or not np.any(detection_mask):
        return photo.convert(THUMBNAIL_MODE)
    flagged = _resize_mask(detection_mask, photo.size)
    tinted = _tint(photo.convert(THUMBNAIL_MODE), flagged)
    if location is not None:
        _draw_box(tinted, location, photo.size)
    return tinted


def make_thumbnail(photo: Image.Image, size: int) -> Image.Image:
    """Return a copy of the photo scaled down to fit inside a square of `size`."""
    thumbnail = photo.convert(THUMBNAIL_MODE).copy()
    thumbnail.thumbnail((size, size), THUMBNAIL_RESAMPLING)
    return thumbnail


def _resize_mask(mask: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """Resize a 2-D mask to the photo size with nearest-neighbour sampling."""
    mask_image = Image.fromarray(mask.astype(np.uint8) * MASK_ON_VALUE)
    resized = mask_image.resize(size, MASK_RESAMPLING)
    return np.asarray(resized) > 0


def _tint(photo: Image.Image, flagged: np.ndarray) -> Image.Image:
    """Blend the tint over the flagged pixels only."""
    base = np.asarray(photo, dtype=np.float32)
    alpha = flagged.astype(np.float32)[..., None] * OVERLAY_OPACITY
    tint = np.array(OVERLAY_TINT, dtype=np.float32)
    blended = base * (1.0 - alpha) + tint * alpha
    return Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8))


def _draw_box(image: Image.Image, location: DefectLocation, size: tuple[int, int]) -> None:
    """Draw the normalized defect box, clamped inside the image."""
    width, height = size
    left, top, right, bottom = location.bbox
    box = [
        _clamp(int(left * width), width),
        _clamp(int(top * height), height),
        _clamp(int(right * width), width),
        _clamp(int(bottom * height), height),
    ]
    ImageDraw.Draw(image).rectangle(box, outline=OVERLAY_TINT, width=BOX_WIDTH_PIXELS)
    logger.debug("Drew defect box %s", box)


def _clamp(value: int, upper: int) -> int:
    """Keep a pixel coordinate inside the image."""
    return max(0, min(upper - 1, value))
