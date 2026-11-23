"""Lazy, per-category detector registry."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from app.core.categories import CategoryCatalog, CategoryConfig
from app.core.config import Settings, get_settings
from app.models.detector import Detector

logger = logging.getLogger(__name__)


class DetectorRegistry:
    """Create and cache one detector per available category."""

    def __init__(
        self,
        catalog: CategoryCatalog,
        device: str,
        factory: Callable[[str, str], Detector] | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Store the catalog, device, settings and an optional test factory."""
        self._catalog = catalog
        self._device = device
        self._settings = settings
        self._factory = factory
        self._cache: dict[str, Detector] = {}
        self._lock = threading.Lock()

    def category(self, category_id: str) -> CategoryConfig:
        """Return the validated config for *category_id*."""
        return self._catalog.get(category_id)

    def get(self, category_id: str) -> Detector:
        """Return the detector for *category_id*, creating it on first use."""
        cached = self._cache.get(category_id)
        if cached is not None:
            return cached
        # Double-checked locking: concurrent first requests for the same
        # category must create and load its detector exactly once.
        with self._lock:
            cached = self._cache.get(category_id)
            if cached is not None:
                return cached
            config = self._catalog.get(category_id)
            detector = (
                self._factory(str(config.checkpoint_path), self._device)
                if self._factory is not None
                else self._default_factory(config)
            )
            self._cache[category_id] = detector
            logger.info("Created detector for category %s", category_id)
            return detector

    def _default_factory(self, config: CategoryConfig) -> Detector:
        """Build the configured detector, importing it only when needed.

        Gemini ignores the checkpoint path entirely, so a category does not need
        a ``.ckpt`` file on disk when ``settings.detector`` selects Gemini.
        """
        from app.models.factory import create_detector

        settings = self._settings if self._settings is not None else get_settings()
        return create_detector(
            Path(config.checkpoint_path),
            self._device,
            settings=settings,
            category=config,
        )
