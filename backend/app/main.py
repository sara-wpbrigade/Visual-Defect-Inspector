"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.categories import router as categories_router
from app.api.dependencies import build_repository
from app.api.errors import register_exception_handlers
from app.api.history import router as history_router
from app.api.inspections import router as inspections_router
from app.core.config import get_settings


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Create or migrate the database schema before serving requests."""
    build_repository(get_settings()).initialize()
    yield


app = FastAPI(title="Visual Defect Inspector", lifespan=lifespan)

app.include_router(inspections_router)
app.include_router(history_router)
app.include_router(categories_router)

register_exception_handlers(app)


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the service is running."""
    return {"status": "ok"}
