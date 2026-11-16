"""FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(title="Visual Defect Inspector")


@app.get("/health")
def health() -> dict[str, str]:
    """Report that the service is running."""
    return {"status": "ok"}
