"""Tests for the annotated overlay and thumbnail rendering."""

import numpy as np
import pytest
from PIL import Image

from app.schemas import DefectLocation
from app.services.overlay import make_thumbnail, render_overlay

PHOTO_SIZE = (20, 20)
BLUE = (0, 0, 255)
RED = (255, 0, 0)


def make_photo(color: tuple[int, int, int] = BLUE) -> Image.Image:
    """Return a solid RGB photo."""
    return Image.new("RGB", PHOTO_SIZE, color)


def make_mask(shape: tuple[int, int] = (10, 10)) -> np.ndarray:
    """Return a 2-D mask with its top-left quarter flagged."""
    mask = np.zeros(shape, dtype=bool)
    mask[0 : shape[0] // 2, 0 : shape[1] // 2] = True
    return mask


def test_overlay_keeps_the_photo_size_and_mode() -> None:
    """The overlay is an RGB image of exactly the photo size."""
    result = render_overlay(make_photo(), make_mask(), None)
    assert (result.mode, result.size) == ("RGB", PHOTO_SIZE)


def test_flagged_pixels_are_tinted_and_clean_pixels_are_untouched() -> None:
    """Only the resized mask region changes, and it shifts towards red."""
    result = render_overlay(make_photo(), make_mask(), None)
    pixels = np.asarray(result)
    flagged = pixels[5, 5]
    clean = pixels[15, 15]
    assert flagged[0] > BLUE[0]
    assert flagged[2] < BLUE[2]
    assert tuple(clean) == BLUE


def test_location_draws_a_box_inside_the_image() -> None:
    """A box reaching the far edge is clamped, not drawn outside the photo."""
    location = DefectLocation(region="center", bbox=(0.0, 0.0, 1.0, 1.0))
    result = render_overlay(make_photo(), make_mask(), location)
    assert result.getpixel((0, 0)) == RED
    assert result.getpixel((PHOTO_SIZE[0] - 1, PHOTO_SIZE[1] - 1)) == RED
    assert result.size == PHOTO_SIZE


@pytest.mark.parametrize(
    "mask",
    [
        np.array([], dtype=bool),
        np.zeros(PHOTO_SIZE, dtype=bool),
        np.ones(5, dtype=bool),
    ],
    ids=["empty-1d", "empty-2d", "non-empty-1d"],
)
def test_unusable_masks_return_an_unchanged_copy(mask: np.ndarray) -> None:
    """An empty or one-dimensional mask leaves every pixel as it was."""
    photo = make_photo()
    result = render_overlay(photo, mask, None)
    assert result is not photo
    assert np.array_equal(np.asarray(result), np.asarray(photo))


def test_thumbnail_fits_inside_the_requested_size() -> None:
    """A wide photo shrinks to the size while keeping its aspect ratio."""
    photo = Image.new("RGB", (400, 200), BLUE)
    thumbnail = make_thumbnail(photo, 160)
    assert thumbnail.size == (160, 80)


def test_thumbnail_never_enlarges_a_small_photo() -> None:
    """A photo smaller than the thumbnail size stays as it is."""
    thumbnail = make_thumbnail(make_photo(), 160)
    assert thumbnail.size == PHOTO_SIZE
