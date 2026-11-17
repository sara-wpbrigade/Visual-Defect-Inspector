"""Validation and decoding of uploaded images."""

import io

from PIL import Image, UnidentifiedImageError

ALLOWED_FORMATS = frozenset({"JPEG", "PNG"})
INVALID_IMAGE_MESSAGE = "The upload is not a valid image."


class InvalidImageError(ValueError):
    """Raised when an upload is not a usable JPEG or PNG image."""


class ImageTooLargeError(InvalidImageError):
    """Raised when an upload exceeds the byte or pixel limits."""


def load_image(data: bytes, *, max_bytes: int, max_pixels: int) -> Image.Image:
    """Validate raw upload bytes and return them as a fresh RGB image.

    The real format is read from the file contents, never from the client's
    filename or content type.

    Raises:
        InvalidImageError: The bytes are empty, corrupt or not JPEG/PNG.
        ImageTooLargeError: The bytes or the decoded pixel count are too large.
    """
    if not data:
        raise InvalidImageError("The uploaded image is empty.")
    if len(data) > max_bytes:
        raise ImageTooLargeError(f"Images must be at most {max_bytes} bytes.")
    image_format = _verify(data)
    if image_format not in ALLOWED_FORMATS:
        raise InvalidImageError(f"Unsupported image format {image_format}; use JPEG or PNG.")
    return _decode(data, max_pixels)


def _verify(data: bytes) -> str:
    """Check that the bytes are an intact image and return its real format."""
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
            return probe.format or ""
    except Image.DecompressionBombError as exc:
        raise ImageTooLargeError("The image has too many pixels.") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise InvalidImageError(INVALID_IMAGE_MESSAGE) from exc


def _decode(data: bytes, max_pixels: int) -> Image.Image:
    """Decode the image, enforce the pixel limit and return RGB pixels."""
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
            if width * height > max_pixels:
                raise ImageTooLargeError(f"Images must be at most {max_pixels} pixels.")
            image.load()
            return image.convert("RGB").copy()
    except Image.DecompressionBombError as exc:
        raise ImageTooLargeError("The image has too many pixels.") from exc
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise InvalidImageError(INVALID_IMAGE_MESSAGE) from exc
