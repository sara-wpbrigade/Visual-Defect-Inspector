"""Shared image-embedding helpers for the maintenance scripts."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from app.models.embedding_classifier import ImageEmbedder

IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"})


def image_paths(folder: Path, *, recursive: bool = False) -> list[Path]:
    """Return the image files in *folder*, optionally including subfolders."""
    if not folder.is_dir():
        return []
    source = folder.rglob("*") if recursive else folder.iterdir()
    return sorted(path for path in source if path.suffix.lower() in IMAGE_SUFFIXES)


def embed_images(embedder: ImageEmbedder, paths: list[Path]) -> list[np.ndarray]:
    """Return one normalised embedding per image path."""
    vectors: list[np.ndarray] = []
    for path in paths:
        with Image.open(path) as image:
            vectors.append(embedder.embed(image.convert("RGB")))
    return vectors
