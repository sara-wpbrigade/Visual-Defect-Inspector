"""Report category-gate similarity statistics and a suggested cutoff.

Usage:
    uv run python -m scripts.calibrate_category_gate

The script only logs its findings; it never edits a category config.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from app.core.categories import CategoryCatalog, CategoryConfig, load_categories
from app.models.embedding_classifier import (
    PROTOTYPE_KEY,
    ImageEmbedder,
    cosine,
    normalise,
)
from scripts.image_embeddings import embed_images, image_paths

logger = logging.getLogger(__name__)

DATASET_DIR = Path("data/mvtec")
TEST_SPLIT = Path("test")
OUT_OF_SCOPE_DIR = Path("data/out_of_scope")
PERCENTILE = 1
MIDPOINT_DIVISOR = 2.0


def _load_prototype(path: Path) -> np.ndarray:
    """Load and normalise one category's mean embedding."""
    with np.load(path) as data:
        if PROTOTYPE_KEY not in data:
            raise ValueError(f"Prototype {path.name} has no '{PROTOTYPE_KEY}' array.")
        return normalise(np.asarray(data[PROTOTYPE_KEY], dtype=np.float64))


def _similarities(vectors: list[np.ndarray], prototype: np.ndarray) -> list[float]:
    """Return the cosine similarity of every vector to one prototype."""
    return [cosine(vector, prototype) for vector in vectors]


def _other_scores(
    vectors: list[np.ndarray],
    category_id: str,
    prototypes: dict[str, np.ndarray],
) -> list[float]:
    """Return similarities between these images and every other category."""
    return [
        cosine(vector, prototype)
        for vector in vectors
        for other_id, prototype in prototypes.items()
        if other_id != category_id
    ]


def _format(value: float | None) -> str:
    """Format an optional similarity for the log line."""
    return "n/a" if value is None else f"{value:.3f}"


def _log_stats(
    category_id: str,
    own: list[float],
    other: list[float],
    outside: list[float],
) -> None:
    """Log the own-category percentiles, outside maximum and recommendation."""
    first_percentile = float(np.percentile(own, PERCENTILE))
    other_max = max(other) if other else None
    outside_max = max(outside) if outside else None
    logger.info(
        "%s own min=%.3f p1=%.3f median=%.3f | other max=%s | outside max=%s",
        category_id,
        min(own),
        first_percentile,
        float(np.median(own)),
        _format(other_max),
        _format(outside_max),
    )
    if outside_max is None:
        logger.info("%s recommended min_similarity=n/a (no outside images)", category_id)
        return
    recommendation = (first_percentile + outside_max) / MIDPOINT_DIVISOR
    logger.info("%s recommended min_similarity=%.3f", category_id, recommendation)


def _report_category(
    config: CategoryConfig,
    prototypes: dict[str, np.ndarray],
    embedder: ImageEmbedder,
    outside_vectors: list[np.ndarray],
) -> None:
    """Log the statistics for one available category."""
    folder = DATASET_DIR / config.id / TEST_SPLIT
    vectors = embed_images(embedder, image_paths(folder, recursive=True))
    if not vectors:
        logger.warning("No test images found for category %s; skipping.", config.id)
        return
    own = _similarities(vectors, prototypes[config.id])
    other = _other_scores(vectors, config.id, prototypes)
    outside = list(other)
    if outside_vectors:
        outside.extend(_similarities(outside_vectors, prototypes[config.id]))
    _log_stats(config.id, own, other, outside)


def _prototypes(catalog: CategoryCatalog) -> dict[str, np.ndarray]:
    """Load every available category's prototype embedding."""
    return {config.id: _load_prototype(config.prototype_path) for config in catalog.all()}


def main() -> None:
    """Load the available categories and log their gate calibration numbers."""
    logging.basicConfig(level=logging.INFO)
    catalog = load_categories()
    if not catalog.all():
        logger.warning("No available categories to calibrate.")
        return
    prototypes = _prototypes(catalog)
    embedder = ImageEmbedder()
    outside_vectors = embed_images(embedder, image_paths(OUT_OF_SCOPE_DIR))
    for config in catalog.all():
        _report_category(config, prototypes, embedder, outside_vectors)


if __name__ == "__main__":
    main()
