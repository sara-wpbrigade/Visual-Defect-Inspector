"""GET /categories - list the categories the operator may choose."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_category_catalog
from app.core.categories import CategoryCatalog

router = APIRouter()


@router.get("/categories")
def list_categories(
    catalog: Annotated[CategoryCatalog, Depends(get_category_catalog)],
) -> list[dict[str, str | list[str]]]:
    """Return the available categories with their display names and defect types."""
    return [
        {
            "id": config.id,
            "display_name": config.display_name,
            "description": config.description,
            "defect_types": list(config.defect_types),
        }
        for config in catalog.all()
    ]
