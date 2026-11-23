"""Embedding-based yes/no category check backed by a timm image encoder."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app.core.categories import CategoryCatalog
from app.models.category_classifier import CategoryClassifier

logger = logging.getLogger(__name__)

BACKBONE_NAME = "wide_resnet50_2.racm_in1k"
AUTO_DEVICE = "auto"
RESIZE_SIDE = 256
CROP_SIZE = 224
PIXEL_SCALE = 255.0
PROTOTYPE_KEY = "mean"
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
RESAMPLING = Image.Resampling.BILINEAR


def normalise(vector: np.ndarray) -> np.ndarray:
    """Return *vector* scaled to unit L2 norm as float64."""
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        raise ValueError("Cannot normalise a zero-length embedding.")
    return np.asarray(vector, dtype=np.float64) / norm


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    """Return the cosine similarity of two vectors in the range -1 to 1."""
    if left.shape != right.shape:
        raise ValueError("Cosine similarity needs two vectors of equal length.")
    return float(np.clip(np.dot(normalise(left), normalise(right)), -1.0, 1.0))


def preprocess(image: Image.Image) -> np.ndarray:
    """Resize to 256, centre crop 224, apply ImageNet stats and return CHW floats."""
    phot = _center_crop(_resize_shorter_side(image.convert("RGB")))
    pixels = np.asarray(phot, dtype=np.float32) / PIXEL_SCALE
    normalised = (pixels - IMAGENET_MEAN) / IMAGENET_STD
    return np.transpose(normalised, (2, 0, 1))


def _resize_shorter_side(image: Image.Image) -> Image.Image:
    """Scale the image so its shorter side is exactly 256 pixels."""
    width, height = image.size
    scale = RESIZE_SIDE / min(width, height)
    size = (max(RESIZE_SIDE, round(width * scale)), max(RESIZE_SIDE, round(height * scale)))
    return image.resize(size, RESAMPLING)


def _center_crop(image: Image.Image) -> Image.Image:
    """Return the central 224 by 224 region of the image."""
    left = (image.width - CROP_SIZE) // 2
    top = (image.height - CROP_SIZE) // 2
    return image.crop((left, top, left + CROP_SIZE, top + CROP_SIZE))


class ImageEmbedder:
    """Lazily load the timm backbone and turn photos into normalised vectors."""

    def __init__(self, device: str = AUTO_DEVICE) -> None:
        """Remember the requested device; the model is loaded on first use."""
        self._device_name = device
        self._device: Any | None = None
        self._model: Any | None = None
        self._load_lock = threading.Lock()

    def embed(self, image: Image.Image) -> np.ndarray:
        """Return the L2-normalised global-pooled embedding of *image*."""
        import torch

        model = self._loaded_model()
        batch = torch.from_numpy(preprocess(image)).unsqueeze(0).to(self._device)
        with torch.inference_mode():
            features = model(batch)
        vector = np.asarray(features[0].detach().cpu().numpy(), dtype=np.float64)
        return normalise(vector)

    def _loaded_model(self) -> Any:
        """Create the timm model once, on the shared device selection."""
        cached = self._model
        if cached is not None:
            return cached
        # Double-checked locking: concurrent first embeddings must not each
        # create (and download) a backbone on the shared device.
        with self._load_lock:
            cached = self._model
            if cached is not None:
                return cached
            import timm

            from app.models.patchcore import resolve_device

            self._device = resolve_device(self._device_name)
            model = timm.create_model(BACKBONE_NAME, pretrained=True, num_classes=0)
            model.eval()
            model.to(self._device)
            self._model = model
            logger.info("Loaded category embedding backbone on %s", self._device)
            return model


class EmbeddingCategoryClassifier(CategoryClassifier):
    """Compare one photo with one category prototype embedding."""

    def __init__(
        self,
        catalog: CategoryCatalog,
        device: str = AUTO_DEVICE,
        embedder: ImageEmbedder | None = None,
    ) -> None:
        """Remember the catalog and create the lazy image embedder."""
        self._catalog = catalog
        self._embedder = embedder or ImageEmbedder(device)
        self._prototypes: dict[str, np.ndarray] = {}
        self._lock = threading.Lock()

    def similarity(self, image: Image.Image, category_id: str) -> float:
        """Return the cosine similarity to the chosen category's prototype."""
        # The shared timm backbone and device are not safe for concurrent
        # inference, and the prototype cache is filled lazily below.
        with self._lock:
            config = self._catalog.get(category_id)
            prototype = self._prototype(config.prototype_path)
            return cosine(self._embedder.embed(image), prototype)

    def _prototype(self, path: Path) -> np.ndarray:
        """Load and cache the normalised mean embedding stored in an npz file."""
        key = str(path)
        cached = self._prototypes.get(key)
        if cached is not None:
            return cached
        with np.load(path) as data:
            if PROTOTYPE_KEY not in data:
                raise ValueError(f"Prototype {path.name} has no '{PROTOTYPE_KEY}' array.")
            prototype = normalise(np.asarray(data[PROTOTYPE_KEY], dtype=np.float64))
        self._prototypes[key] = prototype
        return prototype
