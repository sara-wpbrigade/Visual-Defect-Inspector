"""Turn domain errors into HTTP responses."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import CategoryError
from app.core.images import ImageTooLargeError, InvalidImageError
from app.services.inspection import DetectionError
from app.services.repository import InspectionNotFoundError
from app.services.storage import StorageError

INVALID_IMAGE_STATUS = 400
IMAGE_TOO_LARGE_STATUS = 413
UNPROCESSABLE_STATUS = 422
DETECTION_FAILED_STATUS = 503
INSPECTION_NOT_FOUND_STATUS = 404
STORAGE_UNAVAILABLE_STATUS = 503


async def _invalid_image(request: Request, exc: Exception) -> JSONResponse:
    """Answer 400 when an upload is not a usable image."""
    del request
    return _error_response(INVALID_IMAGE_STATUS, exc)


async def _image_too_large(request: Request, exc: Exception) -> JSONResponse:
    """Answer 413 when an upload is over the byte or pixel limit."""
    del request
    return _error_response(IMAGE_TOO_LARGE_STATUS, exc)


async def _detection_failed(request: Request, exc: Exception) -> JSONResponse:
    """Answer 503 when the model could not analyse the image."""
    del request
    return _error_response(DETECTION_FAILED_STATUS, exc)


async def _inspection_not_found(request: Request, exc: Exception) -> JSONResponse:
    """Answer 404 when an inspection id is malformed or unknown."""
    del request
    return _error_response(INSPECTION_NOT_FOUND_STATUS, exc)


async def _storage_unavailable(request: Request, exc: Exception) -> JSONResponse:
    """Answer 503 when the inspection store cannot be read or written."""
    del request
    return _error_response(STORAGE_UNAVAILABLE_STATUS, exc)


async def _category_error(request: Request, exc: Exception) -> JSONResponse:
    """Answer 422 with the structured category error body."""
    del request
    if not isinstance(exc, CategoryError):
        return _error_response(UNPROCESSABLE_STATUS, exc)
    return _error_response(UNPROCESSABLE_STATUS, exc, exc.body.model_dump())


def _error_response(
    status_code: int,
    exc: Exception,
    extra: dict[str, object] | None = None,
) -> JSONResponse:
    """Build a detail body, adding any structured fields the error carries."""
    content: dict[str, object] = {"detail": str(exc)}
    if extra is not None:
        content.update(extra)
    return JSONResponse(status_code=status_code, content=content)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the domain error handlers to the application."""
    app.add_exception_handler(InvalidImageError, _invalid_image)
    app.add_exception_handler(ImageTooLargeError, _image_too_large)
    app.add_exception_handler(DetectionError, _detection_failed)
    app.add_exception_handler(InspectionNotFoundError, _inspection_not_found)
    app.add_exception_handler(StorageError, _storage_unavailable)
    app.add_exception_handler(CategoryError, _category_error)
