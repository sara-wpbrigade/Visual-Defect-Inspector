"""Lazy, per-category detector registry."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from app.core.categories import CategoryCatalog, CategoryConfig
from app.models.detector import Detector

logger = logging.getLogger(__name__)


class DetectorRegistry:
    """Create and cache one detector per available category."""

    def __init__(
        self,
        catalog: CategoryCatalog,
        device: str,
        factory: Callable[[str, str], Detector] | None = None,
    ) -> None:
        """Store the catalog, device and an optional test factory."""
        self._catalog = catalog
        self._device = device
        self._factory = factory or self._default_factory
        self._cache: dict[str, Detector] = {}

    def category(self, category_id: str) -> CategoryConfig:
        """Return the validated config for *category_id*."""
        return self._catalog.get(category_id)

    def get(self, category_id: str) -> Detector:
        """Return the detector for *category_id*, creating it on first use."""
        cached = self._cache.get(category_id)
        if cached is not None:
            return cached
        config = self._catalog.get(category_id)
        detector = self._factory(str(config.checkpoint_path), self._device)
        self._cache[category_id] = detector
        logger.info("Created detector for category %s", category_id)
        return detector

    @staticmethod
    def _default_factory(checkpoint: str, device: str) -> Detector:
        """Build the real PatchCore detector, importing it only when needed."""
        from app.models.factory import create_detector

        return create_detector(Path(checkpoint), device)
