"""Pick the detector implementation named by configuration."""

from app.core.config import Settings
from app.models.detector import Detector


def create_detector(settings: Settings) -> Detector:
    """Return the configured detector.

    The import is deferred because loading Anomalib and Torch costs seconds and
    hundreds of megabytes, which the health check and the test suite never need.
    """
    from app.models.patchcore import PatchCoreDetector

    return PatchCoreDetector(settings.checkpoint_path, settings.detector_device)
