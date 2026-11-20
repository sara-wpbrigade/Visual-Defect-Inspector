"""Structured error bodies returned by the category gate."""

from pydantic import BaseModel, Field


class SupportedCategory(BaseModel):
    """One category the operator may choose from."""

    id: str
    display_name: str


class CategoryErrorBody(BaseModel):
    """The JSON body of an unknown-category or category-mismatch response."""

    detail: str
    code: str = Field(..., description="error identifier")
    supported_categories: list[SupportedCategory]
