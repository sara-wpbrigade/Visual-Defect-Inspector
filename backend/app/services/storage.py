"""Storage of inspection photos, overlays and thumbnails."""

import logging
import re
from pathlib import Path
from uuid import uuid4

from PIL import Image

logger = logging.getLogger(__name__)

INSPECTION_ID_PATTERN_TEXT = r"^[0-9a-f]{32}$"
INSPECTION_ID_PATTERN = re.compile(INSPECTION_ID_PATTERN_TEXT)

PHOTO_KIND = "photo"
OVERLAY_KIND = "overlay"
THUMBNAIL_KIND = "thumbnail"
REPORT_KIND = "report"

ARTIFACT_NAMES = {
    PHOTO_KIND: "{inspection_id}.png",
    OVERLAY_KIND: "{inspection_id}_overlay.png",
    THUMBNAIL_KIND: "{inspection_id}_thumb.jpg",
    REPORT_KIND: "{inspection_id}_report.pdf",
}
ARTIFACT_FORMATS = {
    PHOTO_KIND: "PNG",
    OVERLAY_KIND: "PNG",
    THUMBNAIL_KIND: "JPEG",
}
ARTIFACT_MEDIA_TYPES = {
    PHOTO_KIND: "image/png",
    OVERLAY_KIND: "image/png",
    THUMBNAIL_KIND: "image/jpeg",
    REPORT_KIND: "application/pdf",
}
ARTIFACT_OPTIONS = {
    THUMBNAIL_KIND: {"quality": 90},
}
INVALID_ID_MESSAGE = "An inspection id must be 32 lowercase hexadecimal characters."
UNKNOWN_KIND_MESSAGE = "Unknown inspection artifact kind."


class StorageError(RuntimeError):
    """Raised when an inspection artifact or record cannot be stored."""


class InvalidInspectionIdError(StorageError):
    """Raised when an id could escape the upload folder."""


def new_inspection_id() -> str:
    """Return a fresh random inspection id."""
    return uuid4().hex


def report_filename(inspection_id: str) -> str:
    """Return the relative filename for a PDF report."""
    return f"{inspection_id}_report.pdf"


def validate_inspection_id(inspection_id: str) -> str:
    """Return the id when it is a safe file name, otherwise raise a domain error."""
    if not INSPECTION_ID_PATTERN.fullmatch(inspection_id):
        raise InvalidInspectionIdError(INVALID_ID_MESSAGE)
    return inspection_id


class ArtifactStore:
    """Store and locate the three images of one inspection under fixed names."""

    def __init__(self, directory: Path) -> None:
        """Remember the folder that holds every artifact."""
        self._directory = directory

    def path_for(self, inspection_id: str, kind: str) -> Path:
        """Return the fixed path for one artifact, rejecting unsafe ids."""
        validate_inspection_id(inspection_id)
        try:
            name = ARTIFACT_NAMES[kind]
        except KeyError as exc:
            raise StorageError(UNKNOWN_KIND_MESSAGE) from exc
        return self._directory / name.format(inspection_id=inspection_id)

    def save(self, image: Image.Image, inspection_id: str, kind: str) -> Path:
        """Write one artifact under its fixed name and return the path."""
        path = self.path_for(inspection_id, kind)
        self._directory.mkdir(parents=True, exist_ok=True)
        image.save(path, format=ARTIFACT_FORMATS[kind], **ARTIFACT_OPTIONS.get(kind, {}))
        logger.info("Stored %s artifact for inspection %s", kind, inspection_id)
        return path

    def save_bytes(self, data: bytes, inspection_id: str, kind: str) -> Path:
        """Write raw bytes under the fixed artifact path and return the path."""
        path = self.path_for(inspection_id, kind)
        self._directory.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        logger.info("Stored raw bytes for %s artifact for %s", kind, inspection_id)
        return path
