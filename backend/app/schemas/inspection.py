"""The inspection result shapes returned by the API."""

from datetime import datetime

from pydantic import BaseModel, Field

from .assessment import InspectionOutcome
from .report import InspectionReport

BATCH_ID_PATTERN = r"^[A-Za-z0-9_-]{1,40}$"
CATEGORY_ID_PATTERN = r"^[a-z][a-z0-9_]{0,40}$"


class InspectionResult(InspectionOutcome):
    """One finished inspection as returned by the API."""

    inspection_id: str = Field(min_length=1)
    category: str = Field(min_length=1)
    report: InspectionReport


class ImageUrls(BaseModel):
    """Relative URLs of the three stored images for one inspection."""

    photo: str
    overlay: str
    thumbnail: str


class InspectionCreated(InspectionResult):
    """One finished inspection, including where its images are stored."""

    created_at: datetime
    batch_id: str | None = None
    images: ImageUrls
