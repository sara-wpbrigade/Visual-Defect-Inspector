"""Custom domain exceptions for the category gate."""

from __future__ import annotations

from app.schemas.errors import CategoryErrorBody, SupportedCategory

UNKNOWN_CATEGORY_CODE = "unknown_category"
CATEGORY_MISMATCH_CODE = "category_mismatch"


class CategoryError(RuntimeError):
    """Base class for category errors that become HTTP 422 responses."""

    def __init__(
        self,
        detail: str,
        code: str,
        supported: list[SupportedCategory],
    ) -> None:
        """Build the structured body shared by every category error."""
        self.body = CategoryErrorBody(
            detail=detail,
            code=code,
            supported_categories=supported,
        )
        super().__init__(detail)


class UnknownCategoryError(CategoryError):
    """Raised when the chosen category id is not available."""

    def __init__(self, category_id: str, supported: list[SupportedCategory]) -> None:
        """Describe an id that is not in the catalog."""
        super().__init__(
            detail=f"Category '{category_id}' is not known.",
            code=UNKNOWN_CATEGORY_CODE,
            supported=supported,
        )


class CategoryMismatchError(CategoryError):
    """Raised when a photo does not look like the chosen category."""

    def __init__(self, display_name: str, supported: list[SupportedCategory]) -> None:
        """Describe a photo whose similarity is below the category cutoff."""
        super().__init__(
            detail=f"This photo does not look like a {display_name}.",
            code=CATEGORY_MISMATCH_CODE,
            supported=supported,
        )
