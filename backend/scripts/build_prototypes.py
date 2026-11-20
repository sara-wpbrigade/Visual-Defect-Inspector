"""Build a category prototype from its normal training images.

Usage:
    uv run python -m scripts.build_prototypes <category> [--limit N]
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np

from app.core.categories import load_category_config
from app.models.embedding_classifier import ImageEmbedder, normalise
from scripts.image_embeddings import embed_images, image_paths

logger = logging.getLogger(__name__)

DATASET_DIR = Path("data/mvtec")
TRAIN_SPLIT = Path("train") / "good"


def _training_images(category: str, limit: int | None) -> list[Path]:
    """Return the normal training images for *category*, optionally capped."""
    folder = DATASET_DIR / category / TRAIN_SPLIT
    if not folder.is_dir():
        raise FileNotFoundError(f"Training image folder not found: {folder}")
    paths = image_paths(folder)
    if not paths:
        raise ValueError(f"No training images found in {folder}")
    return paths[:limit] if limit is not None else paths


def build_prototype(category: str, limit: int | None = None) -> Path:
    """Embed the category's normal images and write its configured npz prototype."""
    config = load_category_config(category)
    paths = _training_images(category, limit)
    vectors = embed_images(ImageEmbedder(), paths)
    prototype = normalise(np.mean(np.stack(vectors), axis=0))
    config.prototype_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(config.prototype_path, mean=prototype)
    logger.info("Wrote %s from %d images", config.prototype_path, len(paths))
    return config.prototype_path


def _positive_int(raw: str) -> int:
    """Parse a strictly positive integer for --limit."""
    value = int(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("--limit must be at least 1")
    return value


def main() -> None:
    """Parse the command line and build the requested category prototype."""
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Build one category prototype.")
    parser.add_argument("category", help="Category id from config/categories")
    parser.add_argument("--limit", type=_positive_int, default=None, help="Use at most N images")
    args = parser.parse_args()
    build_prototype(args.category, args.limit)


if __name__ == "__main__":
    main()
