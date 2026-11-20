"""HTTP routes for browsing stored inspections and downloading their images."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse

from app.api.dependencies import get_artifact_store, get_repository
from app.schemas import BATCH_ID_PATTERN, CATEGORY_ID_PATTERN
from app.services.repository import (
    RECORD_NOT_FOUND_MESSAGE,
    InspectionDetail,
    InspectionHistory,
    InspectionNotFoundError,
    InspectionRecord,
    InspectionRepository,
    image_urls,
)
from app.services.storage import (
    ARTIFACT_MEDIA_TYPES,
    ArtifactStore,
    InvalidInspectionIdError,
)

router = APIRouter(prefix="/inspections", tags=["inspections"])

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
DEFAULT_OFFSET = 0
IMAGE_NOT_FOUND_MESSAGE = "The inspection image was not found."


@router.get("", response_model=InspectionHistory)
def list_inspections(
    repository: Annotated[InspectionRepository, Depends(get_repository)],
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = DEFAULT_OFFSET,
    batch_id: Annotated[str | None, Query(pattern=BATCH_ID_PATTERN)] = None,
    category: Annotated[str | None, Query(pattern=CATEGORY_ID_PATTERN)] = None,
) -> InspectionHistory:
    """Return one page of the inspection history and the total count."""
    return InspectionHistory(
        items=repository.list(limit=limit, offset=offset, batch_id=batch_id, category=category),
        total=repository.count(batch_id=batch_id, category=category),
    )


@router.get("/{inspection_id}", response_model=InspectionDetail)
def get_inspection(
    inspection_id: str,
    repository: Annotated[InspectionRepository, Depends(get_repository)],
) -> InspectionDetail:
    """Return one stored inspection with its image URLs."""
    try:
        record = repository.get(inspection_id)
    except InvalidInspectionIdError as exc:
        raise InspectionNotFoundError(RECORD_NOT_FOUND_MESSAGE) from exc
    if record is None:
        raise InspectionNotFoundError(RECORD_NOT_FOUND_MESSAGE)
    return _detail(record)


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


def _detail(record: InspectionRecord) -> InspectionDetail:
    """Attach the image URLs to one stored record."""
    return InspectionDetail(**record.model_dump(), images=image_urls(record.id))


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
