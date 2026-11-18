"""HTTP route for creating one inspection."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from PIL import Image

from app.api.dependencies import get_inspection_service, get_report_service
from app.core.config import Settings, get_settings
from app.core.images import load_image
from app.schemas import InspectionResult
from app.services.inspection import InspectionService
from app.services.report import ReportService
from app.services.storage import save_image

router = APIRouter(prefix="/inspections", tags=["inspections"])


@router.post("", response_model=InspectionResult, status_code=201)
def create_inspection(
    image: Annotated[UploadFile, File(description="JPEG or PNG photo of the item")],
    service: Annotated[InspectionService, Depends(get_inspection_service)],
    report_service: Annotated[ReportService, Depends(get_report_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> InspectionResult:
    """Validate and store the photo, then return the facts and the report."""
    # A sync endpoint runs in FastAPI's threadpool, so model inference cannot
    # block the event loop. One byte over the limit proves the file is too big.
    photo = _load_upload(image, settings)
    inspection_id = save_image(photo, settings.upload_dir)
    outcome = service.inspect(photo)
    report = report_service.generate(inspection_id, outcome, photo)
    return InspectionResult(
        inspection_id=inspection_id,
        score=outcome.score,
        assessment=outcome.assessment,
        report=report,
    )


def _load_upload(image: UploadFile, settings: Settings) -> Image.Image:
    """Read at most one byte over the limit, then validate the real bytes."""
    data = image.file.read(settings.max_image_bytes + 1)
    return load_image(
        data, max_bytes=settings.max_image_bytes, max_pixels=settings.max_image_pixels
    )
