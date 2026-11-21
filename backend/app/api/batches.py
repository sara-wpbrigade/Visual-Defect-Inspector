"""HTTP routes for batch queries and details."""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.dependencies import get_artifact_store, get_persona, get_repository
from app.core.persona import PersonaConfig
from app.schemas import BATCH_ID_PATTERN
from app.services.batch import BatchSummary, decide_batch, summarize_batch
from app.services.repository import (
    InspectionDetail,
    InspectionRecord,
    InspectionRepository,
    image_urls,
)
from app.services.storage import REPORT_KIND, ArtifactStore

router = APIRouter(prefix="/batches", tags=["batches"])
BATCH_REGEX = re.compile(BATCH_ID_PATTERN)
BATCH_NOT_FOUND_MESSAGE = "Batch not found."


class BatchDetailResponse(BaseModel):
    """A batch summary along with all of its inspection items."""

    summary: BatchSummary
    items: list[InspectionDetail]


@router.get("", response_model=list[BatchSummary])
def list_batches(
    repository: Annotated[InspectionRepository, Depends(get_repository)],
    persona: Annotated[PersonaConfig, Depends(get_persona)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[BatchSummary]:
    """Return summaries for all batches, ordered by most recent inspection."""
    batch_ids = repository.list_batches(limit=limit, offset=offset)
    summaries: list[BatchSummary] = []
    for b_id in batch_ids:
        items = repository.items_in_batch(b_id)
        if items:
            summaries.append(summarize_batch(b_id, items, persona.batch_policy))
    return summaries


@router.get("/{batch_id}", response_model=BatchDetailResponse)
def get_batch(
    batch_id: str,
    repository: Annotated[InspectionRepository, Depends(get_repository)],
    persona: Annotated[PersonaConfig, Depends(get_persona)],
    store: Annotated[ArtifactStore, Depends(get_artifact_store)],
) -> BatchDetailResponse:
    """Return summary and item details for one validated batch id."""
    if not BATCH_REGEX.fullmatch(batch_id):
        raise HTTPException(status_code=404, detail=BATCH_NOT_FOUND_MESSAGE)

    items = repository.items_in_batch(batch_id)
    if not items:
        raise HTTPException(status_code=404, detail=BATCH_NOT_FOUND_MESSAGE)

    summary = summarize_batch(batch_id, items, persona.batch_policy)
    detailed_items = [_to_detail(item, items, persona, store) for item in items]
    return BatchDetailResponse(summary=summary, items=detailed_items)


def _to_detail(
    record: InspectionRecord,
    items: list[InspectionRecord],
    persona: PersonaConfig,
    store: ArtifactStore,
) -> InspectionDetail:
    """Attach URLs and read-time flags to a batch inspection item."""
    decision = decide_batch(items, persona.batch_policy).value
    pdf_avail = bool(record.report_pdf_path and store.path_for(record.id, REPORT_KIND).is_file())
    pdf_url = f"/inspections/{record.id}/report.pdf" if pdf_avail else None
    return InspectionDetail(
        **record.model_dump(),
        images=image_urls(record.id),
        batch_decision=decision,
        report_pdf_available=pdf_avail,
        report_pdf_url=pdf_url,
    )
