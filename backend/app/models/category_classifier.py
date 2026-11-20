"""The category classifier interface: how similar is a photo to a prototype."""

from typing import Protocol

from PIL import Image


class CategoryClassifier(Protocol):
    """Decide how closely one photo resembles one category prototype."""

    def similarity(self, image: Image.Image, category_id: str) -> float:
        """Return the cosine similarity between the photo and the category prototype."""
        ...
