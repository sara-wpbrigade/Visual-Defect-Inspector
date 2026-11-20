"""HTTP route for creating one inspection."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from PIL import Image

from app.api.dependencies import (
    get_artifact_store,
    get_category_verifier,
    get_inspection_service,
    get_report_service,
    get_repository,
)
from app.core.config import Settings, get_settings
from app.core.images import load_image
from app.schemas import (
    BATCH_ID_PATTERN,
    CATEGORY_ID_PATTERN,
    InspectionCreated,
    InspectionOutcome,
    InspectionReport,
)
from app.schemas.errors import CategoryErrorBody
from app.services.category_verifier import CategoryVerifier
from app.services.inspection import InspectionAnalysis, InspectionService
from app.services.overlay import make_thumbnail, render_overlay
from app.services.report import ReportService, utc_now
from app.services.repository import InspectionRecord, InspectionRepository, image_urls
from app.services.storage import (
    OVERLAY_KIND,
    PHOTO_KIND,
    THUMBNAIL_KIND,
    ArtifactStore,
    new_inspection_id,
)

router = APIRouter(prefix="/inspections", tags=["inspections"])


@router.post(
    "",
    response_model=InspectionCreated,
    responses={422: {"model": CategoryErrorBody}},
    status_code=201,
)
def create_inspection(
    image: Annotated[UploadFile, File(description="JPEG or PNG photo of the item")],
    service: Annotated[InspectionService, Depends(get_inspection_service)],
    report_service: Annotated[ReportService, Depends(get_report_service)],
    verifier: Annotated[CategoryVerifier, Depends(get_category_verifier)],
    store: Annotated[ArtifactStore, Depends(get_artifact_store)],
    repository: Annotated[InspectionRepository, Depends(get_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
    category: Annotated[
        str,
        Form(pattern=CATEGORY_ID_PATTERN, description="Category chosen by the operator"),
    ],
    batch_id: Annotated[str | None, Form(pattern=BATCH_ID_PATTERN)] = None,
) -> InspectionCreated:
    """Validate the photo and category, analyse it, then persist the inspection."""
    # A sync endpoint runs in FastAPI's threadpool, so model inference cannot
    # block the event loop. One byte over the limit proves the file is too big.
    photo = _load_upload(image, settings)
    verifier.verify(photo, category)
    inspection_id = new_inspection_id()
    analysis = service.inspect(photo, category)
    report = report_service.generate(
        inspection_id, analysis.outcome, photo, persona=analysis.persona
    )
    store.save(photo, inspection_id, PHOTO_KIND)
    _save_artifacts(store, photo, analysis, inspection_id, settings.thumbnail_size)
    created_at = utc_now()
    repository.add(
        _build_record(
            inspection_id,
            created_at,
            analysis.persona.name,
            category,
            batch_id,
            analysis.outcome,
            report,
        )
    )
    return _created_result(inspection_id, category, analysis.outcome, report, created_at, batch_id)


def _created_result(
    inspection_id: str,
    category: str,
    outcome: InspectionOutcome,
    report: InspectionReport,
    created_at: datetime,
    batch_id: str | None,
) -> InspectionCreated:
    """Build the response body for a stored inspection."""
    return InspectionCreated(
        inspection_id=inspection_id,
        category=category,
        score=outcome.score,
        assessment=outcome.assessment,
        report=report,
        created_at=created_at,
        batch_id=batch_id,
        images=image_urls(inspection_id),
    )


def _load_upload(image: UploadFile, settings: Settings) -> Image.Image:
    """Read at most one byte over the limit, then validate the real bytes."""
    data = image.file.read(settings.max_image_bytes + 1)
    return load_image(
        data, max_bytes=settings.max_image_bytes, max_pixels=settings.max_image_pixels
    )


def _save_artifacts(
    store: ArtifactStore,
    photo: Image.Image,
    analysis: InspectionAnalysis,
    inspection_id: str,
    thumbnail_size: int,
) -> None:
    """Write the annotated overlay and the thumbnail next to the photo."""
    location = analysis.outcome.assessment.location
    store.save(
        render_overlay(photo, analysis.detection.mask, location), inspection_id, OVERLAY_KIND
    )
    store.save(make_thumbnail(photo, thumbnail_size), inspection_id, THUMBNAIL_KIND)


def _build_record(
    inspection_id: str,
    created_at: datetime,
    persona: str,
    category: str,
    batch_id: str | None,
    outcome: InspectionOutcome,
    report: InspectionReport,
) -> InspectionRecord:
    """Assemble the record that is persisted for this inspection."""
    return InspectionRecord(
        id=inspection_id,
        created_at=created_at,
        persona=persona,
        category=category,
        batch_id=batch_id,
        score=outcome.score,
        assessment=outcome.assessment,
        report=report,
    )
