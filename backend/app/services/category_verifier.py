"""The yes/no category gate checked before an inspection is stored."""

from __future__ import annotations

import logging

from PIL import Image

from app.core.categories import CategoryCatalog
from app.core.exceptions import CategoryMismatchError, UnknownCategoryError
from app.models.category_classifier import CategoryClassifier
from app.schemas.errors import SupportedCategory

logger = logging.getLogger(__name__)


class CategoryVerifier:
    """Check that one photo belongs to the category the operator chose."""

    def __init__(self, catalog: CategoryCatalog, classifier: CategoryClassifier) -> None:
        """Remember the available categories and the similarity classifier."""
        self._catalog = catalog
        self._classifier = classifier

    def verify(self, image: Image.Image, category_id: str) -> None:
        """Raise a domain error unless *image* matches *category_id*.

        Only the chosen category is scored; no other category is compared.

        Raises:
            UnknownCategoryError: The id is not one of the available categories.
            CategoryMismatchError: The similarity is below the category cutoff.
        """
        try:
            config = self._catalog.get(category_id)
        except KeyError as exc:
            raise UnknownCategoryError(category_id, self._supported()) from exc
        similarity = self._classifier.similarity(image, category_id)
        logger.info("Category gate category=%s similarity=%.3f", category_id, similarity)
        if similarity < config.min_similarity:
            raise CategoryMismatchError(config.display_name, self._supported())

    def _supported(self) -> list[SupportedCategory]:
        """Return the category list carried by every gate error."""
        return [
            SupportedCategory(id=config.id, display_name=config.display_name)
            for config in self._catalog.all()
        ]
