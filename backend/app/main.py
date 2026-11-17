"""FastAPI application entry point."""

from fastapi import FastAPI

from app.api.errors import register_exception_handlers
from app.api.inspections import router as inspections_router

app = FastAPI(title="Visual Defect Inspector")
app.include_router(inspections_router)
register_exception_handlers(app)


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the service is running."""
    return {"status": "ok"}
