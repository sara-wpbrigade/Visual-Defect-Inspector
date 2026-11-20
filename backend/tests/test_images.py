"""Tests for upload validation."""

import io

import pytest
from PIL import Image

from app.core.images import ImageTooLargeError, InvalidImageError, load_image

MAX_BYTES = 1024 * 1024
MAX_PIXELS = 100 * 100


def make_image(size: tuple[int, int] = (10, 10), image_format: str = "PNG") -> bytes:
    """Return a valid image of the requested size and format as bytes."""
    buffer = io.BytesIO()
    Image.new("RGB", size, color=(180, 60, 60)).save(buffer, format=image_format)
    return buffer.getvalue()


def load(data: bytes) -> Image.Image:
    """Call load_image with the limits used by these tests."""
    return load_image(data, max_bytes=MAX_BYTES, max_pixels=MAX_PIXELS)


def test_valid_png_becomes_rgb() -> None:
    """A valid PNG is decoded and converted to RGB."""
    image = load(make_image())
    assert (image.mode, image.size) == ("RGB", (10, 10))


def test_jpeg_is_accepted() -> None:
    """JPEG is the other allowed real format."""
    image = load(make_image(image_format="JPEG"))
    assert image.mode == "RGB"


def test_empty_upload_is_rejected() -> None:
    """Empty bytes are an error, not an empty image."""
    with pytest.raises(InvalidImageError):
        load(b"")


def test_non_image_bytes_are_rejected() -> None:
    """Plain text is not an image."""
    with pytest.raises(InvalidImageError):
        load(b"this is not an image")


def test_unsupported_format_is_rejected() -> None:
    """A real but unsupported format (GIF) is refused."""
    with pytest.raises(InvalidImageError):
        load(make_image(image_format="GIF"))


def test_corrupt_image_is_rejected() -> None:
    """A truncated PNG fails to decode."""
    with pytest.raises(InvalidImageError):
        load(make_image()[:40])


def test_oversized_upload_is_rejected() -> None:
    """Bytes over the limit are refused before decoding."""
    with pytest.raises(ImageTooLargeError):
        load(b"\x00" * (MAX_BYTES + 1))


def test_too_many_pixels_are_rejected() -> None:
    """A small file can still decode to an enormous image."""
    with pytest.raises(ImageTooLargeError):
        load(make_image((200, 200)))


@pytest.mark.parametrize(
    "data",
    [
        b"<svg xmlns='http://www.w3.org/2000/svg'></svg>",
        b"  \n\t<svg></svg>",
        b"\xef\xbb\xbf<?xml version='1.0'?><svg></svg>",
        b"  \xef\xbb\xbf  <svg></svg>",
    ],
)
def test_svg_is_rejected_with_a_specific_message(data: bytes) -> None:
    """SVG bytes are refused before decoding, with an actionable message."""
    with pytest.raises(
        InvalidImageError, match="SVG images are not supported; upload a JPEG or PNG photo."
    ):
        load(data)


@pytest.mark.parametrize("image_format", ["GIF", "WEBP", "BMP", "TIFF"])
def test_other_real_formats_name_the_format(image_format: str) -> None:
    """Real but unsupported formats keep the format-specific message."""
    with pytest.raises(InvalidImageError, match=f"Unsupported image format {image_format}"):
        load(make_image(image_format=image_format))


def test_pdf_is_rejected_as_an_unsupported_format() -> None:
    """PDF bytes are identified and refused as a document, not a photo."""
    with pytest.raises(InvalidImageError, match="Unsupported image format PDF"):
        load(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n")


def test_text_file_named_png_is_rejected() -> None:
    """A .png filename cannot make ordinary text an image."""
    with pytest.raises(InvalidImageError, match="valid image"):
        load(b"this is not an image")
