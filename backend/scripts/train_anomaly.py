"""Train a PatchCore anomaly model on one MVTec AD category."""

import logging
import sys

from anomalib.data import MVTecAD
from anomalib.engine import Engine
from anomalib.models import Patchcore

logger = logging.getLogger(__name__)

DATASET_ROOT = "data/mvtec"
TRAIN_BATCH_SIZE = 16
EVAL_BATCH_SIZE = 16
NUM_WORKERS = 0
CORESET_SAMPLING_RATIO = 0.01


def train(category: str) -> None:
    """Fit PatchCore on the good images of a category, then evaluate it."""
    datamodule = MVTecAD(
        root=DATASET_ROOT,
        category=category,
        train_batch_size=TRAIN_BATCH_SIZE,
        eval_batch_size=EVAL_BATCH_SIZE,
        num_workers=NUM_WORKERS,
    )
    model = Patchcore(coreset_sampling_ratio=CORESET_SAMPLING_RATIO)
    engine = Engine()
    engine.fit(datamodule=datamodule, model=model)
    results = engine.test(datamodule=datamodule, model=model)
    logger.info("Test results for %s: %s", category, results)


def main() -> None:
    """Train on the category named on the command line."""
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) != 2:
        sys.exit("Usage: uv run python -m scripts.train_anomaly <category>")
    train(sys.argv[1])


if __name__ == "__main__":
    main()
