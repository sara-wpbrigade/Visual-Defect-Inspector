"""HTTP routes for browsing stored inspections and downloading their images."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.dependencies import get_artifact_store, get_persona, get_repository
from app.core.persona import PersonaConfig
from app.schemas import BATCH_ID_PATTERN, CATEGORY_ID_PATTERN
from app.services.batch import decide_batch
from app.services.repository import (
    RECORD_NOT_FOUND_MESSAGE,
    InspectionDetail,
    InspectionHistory,
    InspectionNotFoundError,
    InspectionRecord,
    InspectionRepository,
    InspectionSummary,
    image_urls,
)
from app.services.storage import (
    ARTIFACT_MEDIA_TYPES,
    REPORT_KIND,
    ArtifactStore,
    InvalidInspectionIdError,
    validate_inspection_id,
)

router = APIRouter(prefix="/inspections", tags=["inspections"])

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
DEFAULT_OFFSET = 0
IMAGE_NOT_FOUND_MESSAGE = "The inspection image was not found."
PDF_NOT_AVAILABLE_MESSAGE = "The PDF report is not available."


@router.get("", response_model=InspectionHistory)
def list_inspections(
    repository: Annotated[InspectionRepository, Depends(get_repository)],
    persona: Annotated[PersonaConfig, Depends(get_persona)],
    store: Annotated[ArtifactStore, Depends(get_artifact_store)],
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = DEFAULT_OFFSET,
    batch_id: Annotated[str | None, Query(pattern=BATCH_ID_PATTERN)] = None,
    category: Annotated[str | None, Query(pattern=CATEGORY_ID_PATTERN)] = None,
) -> InspectionHistory:
    """Return one page of the inspection history with read-time batch decision and PDF info."""
    records = repository.list(limit=limit, offset=offset, batch_id=batch_id, category=category)
    summaries = [_summary(r, repository, persona, store) for r in records]
    return InspectionHistory(items=summaries, total=repository.count(batch_id, category))


@router.get("/{inspection_id}/report.pdf")
def get_pdf_report(
    inspection_id: str,
    repository: Annotated[InspectionRepository, Depends(get_repository)],
    store: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> FileResponse:
    """Return the generated PDF report as an inline file response."""
    try:
        validated_id = validate_inspection_id(inspection_id)
        record = repository.get(validated_id)
    except InvalidInspectionIdError as exc:
        raise HTTPException(status_code=404, detail=PDF_NOT_AVAILABLE_MESSAGE) from exc
    if record is None or record.report_pdf_path is None:
        raise HTTPException(status_code=404, detail=PDF_NOT_AVAILABLE_MESSAGE)
    file_path = store.path_for(validated_id, REPORT_KIND)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=PDF_NOT_AVAILABLE_MESSAGE)
    return FileResponse(
        file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="inspection-{validated_id}.pdf"'},
    )


@router.get("/{inspection_id}", response_model=InspectionDetail)
def get_inspection(
    inspection_id: str,
    repository: Annotated[InspectionRepository, Depends(get_repository)],
    persona: Annotated[PersonaConfig, Depends(get_persona)],
    store: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> InspectionDetail:
    """Return one stored inspection with its image URLs and read-time PDF availability."""
    try:
        record = repository.get(inspection_id)
    except InvalidInspectionIdError as exc:
        raise InspectionNotFoundError(RECORD_NOT_FOUND_MESSAGE) from exc
    if record is None:
        raise InspectionNotFoundError(RECORD_NOT_FOUND_MESSAGE)
    return _detail(record, repository, persona, store)


@router.get("/{inspection_id}/{kind}")
def get_image(
    inspection_id: str,
    kind: str,
    store: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> FileResponse:
    """Return the photo, the annotated overlay or the thumbnail."""
    return FileResponse(
        _artifact_path(store, inspection_id, kind), media_type=ARTIFACT_MEDIA_TYPES[kind]
    )


def _detail(
    record: InspectionRecord,
    repository: InspectionRepository,
    persona: PersonaConfig,
    store: ArtifactStore,
) -> InspectionDetail:
    """Attach URLs and evaluated read-time fields to a record."""
    b_items = repository.items_in_batch(record.batch_id) if record.batch_id else [record]
    decision = decide_batch(b_items, persona.batch_policy).value
    pdf_avail = bool(record.report_pdf_path and store.path_for(record.id, REPORT_KIND).is_file())
    pdf_url = f"/inspections/{record.id}/report.pdf" if pdf_avail else None
    return InspectionDetail(
        **record.model_dump(),
        images=image_urls(record.id),
        batch_decision=decision,
        report_pdf_available=pdf_avail,
        report_pdf_url=pdf_url,
    )


def _summary(
    record: InspectionRecord,
    repository: InspectionRepository,
    persona: PersonaConfig,
    store: ArtifactStore,
) -> InspectionSummary:
    """Convert one record to a history summary."""
    b_items = repository.items_in_batch(record.batch_id) if record.batch_id else [record]
    decision = decide_batch(b_items, persona.batch_policy).value
    pdf_avail = bool(record.report_pdf_path and store.path_for(record.id, REPORT_KIND).is_file())
    pdf_url = f"/inspections/{record.id}/report.pdf" if pdf_avail else None
    return InspectionSummary(
        id=record.id,
        created_at=record.created_at,
        category=record.category,
        batch_id=record.batch_id,
        verdict=record.assessment.verdict,
        severity=record.assessment.severity,
        action=record.assessment.action,
        confidence=record.assessment.confidence,
        needs_review=record.assessment.needs_review,
        thumbnail_url=f"/inspections/{record.id}/thumbnail",
        batch_decision=decision,
        report_pdf_available=pdf_avail,
        report_pdf_url=pdf_url,
    )


def _artifact_path(store: ArtifactStore, inspection_id: str, kind: str) -> Path:
    """Return the artifact file, or raise a 404 domain error."""
    if kind not in ARTIFACT_MEDIA_TYPES:
        raise InspectionNotFoundError(IMAGE_NOT_FOUND_MESSAGE)
    try:
        path = store.path_for(inspection_id, kind)
    except InvalidInspectionIdError as exc:
        raise InspectionNotFoundError(IMAGE_NOT_FOUND_MESSAGE) from exc
    if not path.is_file():
        raise InspectionNotFoundError(IMAGE_NOT_FOUND_MESSAGE)
    return path
