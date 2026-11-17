"""Run a trained PatchCore model on one image and save a heatmap overlay."""

import logging
import sys
from pathlib import Path

import numpy as np
from anomalib.data import PredictDataset
from anomalib.engine import Engine
from anomalib.models import Patchcore
from PIL import Image

logger = logging.getLogger(__name__)

IMAGE_SIZE = (256, 256)
MAX_ALPHA = 0.6
EPSILON = 1e-8
OUTPUT_DIR = Path("data/outputs")
RED = (255.0, 0.0, 0.0)


def save_overlay(image_path: Path, anomaly_map: np.ndarray, out_path: Path) -> None:
    """Blend a red heat layer over the photo, stronger where the model sees anomalies."""
    height, width = anomaly_map.shape
    spread = max(float(anomaly_map.max() - anomaly_map.min()), EPSILON)
    heat = (anomaly_map - anomaly_map.min()) / spread
    photo = Image.open(image_path).convert("RGB").resize((width, height))
    base = np.asarray(photo, dtype=np.float32)
    alpha = (heat * MAX_ALPHA)[..., None]
    blended = base * (1 - alpha) + np.array(RED, dtype=np.float32) * alpha
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(blended.astype(np.uint8)).save(out_path)


def predict(ckpt_path: Path, image_path: Path) -> None:
    """Score one image and write its heatmap overlay to the outputs folder."""
    engine = Engine()
    dataset = PredictDataset(path=image_path, image_size=IMAGE_SIZE)
    predictions = engine.predict(model=Patchcore(), dataset=dataset, ckpt_path=ckpt_path)
    if not predictions:
        raise RuntimeError("The model returned no predictions.")
    batch = predictions[0]
    anomaly_map = np.asarray(batch.anomaly_map[0].squeeze().cpu())
    out_path = OUTPUT_DIR / f"{image_path.parent.name}_{image_path.stem}_overlay.png"
    save_overlay(image_path, anomaly_map, out_path)
    area = float(batch.pred_mask[0].float().mean())
    logger.info(
        "score=%.4f label=%d area=%.4f overlay=%s",
        float(batch.pred_score[0]),
        int(batch.pred_label[0]),
        area,
        out_path,
    )


def main() -> None:
    """Predict on the checkpoint and image given on the command line."""
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) != 3:
        sys.exit("Usage: uv run python -m scripts.predict_one <checkpoint> <image>")
    predict(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
