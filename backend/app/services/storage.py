"""Storage of uploaded inspection photos."""

import logging
from pathlib import Path
from uuid import uuid4

from PIL import Image

logger = logging.getLogger(__name__)

STORE_FORMAT = "PNG"
STORE_SUFFIX = ".png"


def save_image(image: Image.Image, directory: Path) -> str:
    """Store an image under a random name and return the new inspection id."""
    inspection_id = uuid4().hex
    directory.mkdir(parents=True, exist_ok=True)
    image.save(directory / f"{inspection_id}{STORE_SUFFIX}", format=STORE_FORMAT)
    logger.info("Stored inspection image %s%s", inspection_id, STORE_SUFFIX)
    return inspection_id
