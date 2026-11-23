"""PatchCore detector: a trained Anomalib model loaded once per process."""

import logging
import threading
from pathlib import Path
from typing import cast

import numpy as np
import torch
from anomalib.models import Patchcore
from PIL import Image
from torchvision.transforms.v2 import Transform

from app.models.detector import Detection

logger = logging.getLogger(__name__)

PIXEL_SCALE = 255.0
AUTO_DEVICE = "auto"


def resolve_device(name: str) -> torch.device:
    """Return the torch device for a config value, picking the best one for 'auto'."""
    if name != AUTO_DEVICE:
        return torch.device(name)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def to_tensor(image: Image.Image) -> torch.Tensor:
    """Convert a PIL image to a float CHW tensor with values from 0 to 1."""
    pixels = np.asarray(image.convert("RGB"), dtype=np.float32) / PIXEL_SCALE
    return torch.from_numpy(pixels).permute(2, 0, 1)


class PatchCoreDetector:
    """Detector implementation backed by an Anomalib PatchCore checkpoint."""

    def __init__(self, checkpoint_path: Path, device: str = AUTO_DEVICE) -> None:
        """Load the checkpoint onto the resolved device and switch to eval mode."""
        if not checkpoint_path.is_file():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        self._device = resolve_device(device)
        self._model = Patchcore.load_from_checkpoint(
            str(checkpoint_path), map_location=self._device
        )
        self._model.eval()
        self._model.to(self._device)
        self._lock = threading.Lock()
        pre_processor = self._model.pre_processor
        post_processor = self._model.post_processor
        if pre_processor is None or post_processor is None:
            raise RuntimeError("The checkpoint has no pre-processor or post-processor.")
        # Use .transform (the training-time path), not the module call: the module
        # call uses Anomalib's export transform and gives slightly different scores.
        transform = pre_processor.transform
        if transform is None:
            raise RuntimeError("The checkpoint has no preprocessing transform.")
        self._transform = cast(Transform, transform)
        self._post_processor = post_processor
        logger.info("Loaded PatchCore checkpoint %s on %s", checkpoint_path.name, self._device)

    def detect(self, image: Image.Image) -> Detection:
        """Score one image and return its heatmap and flagged-pixel mask."""
        # The loaded model and its device hold shared inference buffers, so this
        # instance scores one image at a time even under concurrent requests.
        with self._lock:
            batch = to_tensor(image).to(self._device).unsqueeze(0)
            with torch.inference_mode():
                prepared, _ = self._transform(batch, None)
                predictions = self._post_processor(self._model.model(prepared))
            score = predictions.pred_score
            anomaly_map = predictions.anomaly_map
            mask = predictions.pred_mask
            if score is None or anomaly_map is None or mask is None:
                raise RuntimeError("PatchCore returned an incomplete prediction.")
            return Detection(
                score=float(score[0]),
                anomaly_map=anomaly_map[0].squeeze().cpu().numpy(),
                mask=mask[0].squeeze().cpu().numpy().astype(bool),
            )
