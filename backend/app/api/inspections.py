"""HTTP route for creating one inspection."""

import csv
import io
import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from PIL import Image

from app.api.dependencies import (
    get_artifact_store,
    get_category_verifier,
    get_inspection_service,
    get_persona,
    get_report_service,
    get_repository,
    get_voice_service,
)
from app.core.audio import DecodedAudio, load_audio
from app.core.config import Settings, get_settings
from app.core.images import load_image
from app.core.persona import PersonaConfig
from app.schemas import (
    BATCH_ID_PATTERN,
    CATEGORY_ID_PATTERN,
    InspectionCreated,
    InspectionOutcome,
    InspectionReport,
    Verdict,
    VoiceNoteResult,
)
from app.schemas.errors import CategoryErrorBody
from app.services.batch import decide_batch
from app.services.category_verifier import CategoryVerifier
from app.services.inspection import InspectionAnalysis, InspectionService
from app.services.overlay import make_thumbnail, render_overlay
from app.services.pdf_report import build_report_pdf
from app.services.report import ReportService, utc_now
from app.services.repository import InspectionRecord, InspectionRepository, image_urls
from app.services.storage import (
    OVERLAY_KIND,
    PHOTO_KIND,
    REPORT_KIND,
    THUMBNAIL_KIND,
    ArtifactStore,
    new_inspection_id,
    report_filename,
)
from app.services.voice import VoiceNoteService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inspections", tags=["inspections"])

CSV_COLUMNS = [
    "inspection_id",
    "created_at",
    "batch_id",
    "batch_decision",
    "category",
    "verdict",
    "severity",
    "defect_type",
    "location_region",
    "confidence_percent",
    "flagged_area_percent",
    "anomaly_score",
    "action",
    "needs_review",
    "report_source",
]
INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
MAX_CSV_ROWS = 10_000


@router.get("/export.csv")
def export_defect_log_csv(
    repository: Annotated[InspectionRepository, Depends(get_repository)],
    persona: Annotated[PersonaConfig, Depends(get_persona)],
    batch_id: Annotated[str | None, Query(pattern=BATCH_ID_PATTERN)] = None,
    category: Annotated[str | None, Query(pattern=CATEGORY_ID_PATTERN)] = None,
    only_defects: bool = True,
) -> Response:
    """Export stored inspections as a CSV defect log with formula injection protection."""
    records = repository.list(limit=MAX_CSV_ROWS, offset=0, batch_id=batch_id, category=category)
    if only_defects:
        records = [r for r in records if r.assessment.verdict is Verdict.DEFECT]
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)
    for rec in records:
        b_items = repository.items_in_batch(rec.batch_id) if rec.batch_id else [rec]
        b_decision = decide_batch(b_items, persona.batch_policy).value
        writer.writerow(_csv_row(rec, b_decision))
    today_str = datetime.now(UTC).strftime("%Y%m%d")
    return Response(
        content=output.getvalue().encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="defect-log-{today_str}.csv"'},
    )


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
    persona: Annotated[PersonaConfig, Depends(get_persona)],
    verifier: Annotated[CategoryVerifier, Depends(get_category_verifier)],
    voice_service: Annotated[VoiceNoteService, Depends(get_voice_service)],
    store: Annotated[ArtifactStore, Depends(get_artifact_store)],
    repository: Annotated[InspectionRepository, Depends(get_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
    category: Annotated[
        str,
        Form(pattern=CATEGORY_ID_PATTERN, description="Category chosen by the operator"),
    ],
    batch_id: Annotated[str | None, Form(pattern=BATCH_ID_PATTERN)] = None,
    voice_note: Annotated[UploadFile | None, File(description="Optional spoken note")] = None,
) -> InspectionCreated:
    """Validate, analyse, and persist one photo, then generate and store its report."""
    # A sync endpoint runs in FastAPI's threadpool, so model inference cannot
    # block the event loop. One byte over the limit proves the file is too big.

    # 1. Validate the photo and the optional voice note before writing anything.
    photo = _load_upload(image, settings)
    audio = _load_voice_note(voice_note, settings)
    verifier.verify(photo, category)

    # 2. Transcribe first: a speech-model failure must leave no stored artifacts.
    voice_result = voice_service.process(audio) if audio is not None else None

    # 3. Setup IDs
    inspection_id = new_inspection_id()
    effective_batch = (
        batch_id.strip() if batch_id and batch_id.strip() else f"batch-{inspection_id[:8]}"
    )

    # 4. Save photo once and run AI analysis
    store.save(photo, inspection_id, PHOTO_KIND)
    analysis = service.inspect(photo, category)
    report = report_service.generate(
        inspection_id,
        analysis.outcome,
        photo,
        transcript=voice_result.text if voice_result is not None else None,
        persona=analysis.persona,
    )
    _save_artifacts(store, photo, analysis, inspection_id, settings.thumbnail_size)

    # 5. Save record to SQLite
    created_at = utc_now()
    record = _build_record(
        inspection_id,
        created_at,
        analysis.persona.name,
        effective_batch,
        category,
        analysis.outcome,
        report,
        voice_result,
    )
    repository.add(record)

    # 6. Task 3: Batch decision & Stored PDF
    batch_items = repository.items_in_batch(effective_batch)
    batch_decision = decide_batch(batch_items, analysis.persona.batch_policy)
    _generate_and_save_pdf(record, store, repository, batch_decision.value)

    # 7. Return response with batch_decision and PDF availability
    return _created_result(
        inspection_id,
        category,
        analysis.outcome,
        report,
        created_at,
        effective_batch,
        batch_decision.value,
        voice_result,
        store,
    )


def _generate_and_save_pdf(
    record: InspectionRecord,
    store: ArtifactStore,
    repository: InspectionRepository,
    decision_text: str,
) -> None:
    """Generate and store the PDF report, logging any error type."""
    try:
        data = build_report_pdf(record, store, decision_text)
        store.save_bytes(data, record.id, REPORT_KIND)
        repository.set_report_pdf_path(record.id, report_filename(record.id))
    except Exception as exc:
        logger.warning("PDF generation failed: %s", type(exc).__name__)


def _created_result(
    inspection_id: str,
    category: str,
    outcome: InspectionOutcome,
    report: InspectionReport,
    created_at: datetime,
    batch_id: str | None,
    batch_decision: str,
    voice_note: VoiceNoteResult | None,
    store: ArtifactStore,
) -> InspectionCreated:
    """Build the response body for the created inspection."""
    pdf_avail = store.path_for(inspection_id, REPORT_KIND).is_file()
    pdf_url = f"/inspections/{inspection_id}/report.pdf" if pdf_avail else None
    return InspectionCreated(
        inspection_id=inspection_id,
        category=category,
        score=outcome.score,
        assessment=outcome.assessment,
        report=report,
        created_at=created_at,
        batch_id=batch_id,
        batch_decision=batch_decision,
        voice_note=voice_note,
        report_pdf_available=pdf_avail,
        report_pdf_url=pdf_url,
        images=image_urls(inspection_id),
    )


def _csv_row(rec: InspectionRecord, batch_decision: str) -> list[str]:
    """Format one inspection row for CSV export."""
    loc = rec.assessment.location
    confidence = f"{rec.assessment.confidence * 100:.1f}%"
    area_ratio = f"{rec.assessment.area_ratio * 100:.1f}%"
    return [
        _sanitize_cell(rec.id),
        _sanitize_cell(rec.created_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")),
        _sanitize_cell(rec.batch_id or ""),
        _sanitize_cell(batch_decision),
        _sanitize_cell(rec.category),
        _sanitize_cell(rec.assessment.verdict.value),
        _sanitize_cell(rec.assessment.severity.value),
        _sanitize_cell(rec.report.content.defect_type or ""),
        _sanitize_cell(loc.region if loc else ""),
        _sanitize_cell(confidence),
        _sanitize_cell(area_ratio),
        _sanitize_cell(f"{rec.score:.3f}"),
        _sanitize_cell(rec.assessment.action.value),
        _sanitize_cell("true" if rec.assessment.needs_review else "false"),
        _sanitize_cell(rec.report.source.value),
    ]


def _sanitize_cell(value: Any) -> str:
    """Escape potential formula injection prefixes."""
    text = "" if value is None else str(value)
    if text.startswith(INJECTION_PREFIXES):
        return f"'{text}"
    return text


def _load_upload(image: UploadFile, settings: Settings) -> Image.Image:
    """Read at most one byte over the limit, then validate the real bytes."""
    data = image.file.read(settings.max_image_bytes + 1)
    return load_image(
        data, max_bytes=settings.max_image_bytes, max_pixels=settings.max_image_pixels
    )


def _load_voice_note(upload: UploadFile | None, settings: Settings) -> DecodedAudio | None:
    """Validate and decode the optional voice note; None when none was sent."""
    if upload is None:
        return None
    data = upload.file.read(settings.max_audio_bytes + 1)
    return load_audio(
        data, max_bytes=settings.max_audio_bytes, max_seconds=settings.max_audio_seconds
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
    batch_id: str | None,
    category: str,
    outcome: InspectionOutcome,
    report: InspectionReport,
    voice_note: VoiceNoteResult | None,
) -> InspectionRecord:
    """Assemble the record that is persisted for this inspection."""
    return InspectionRecord(
        id=inspection_id,
        created_at=created_at,
        persona=persona,
        batch_id=batch_id,
        category=category,
        score=outcome.score,
        assessment=outcome.assessment,
        report=report,
        voice_note=voice_note,
    )
