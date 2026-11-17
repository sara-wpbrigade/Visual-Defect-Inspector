"""Tests for the PatchCore helpers that need no checkpoint."""

from PIL import Image

from app.models.patchcore import AUTO_DEVICE, resolve_device, to_tensor


def test_to_tensor_is_channel_first_and_scaled() -> None:
    """White pixels become a float CHW tensor in the 0 to 1 range."""
    tensor = to_tensor(Image.new("RGB", (8, 4), color=(255, 255, 255)))
    assert tuple(tensor.shape) == (3, 4, 8)
    assert set(tensor.flatten().tolist()) == {1.0}


def test_to_tensor_expands_greyscale_to_rgb() -> None:
    """A single-channel image is expanded to three channels."""
    tensor = to_tensor(Image.new("L", (4, 4), color=0))
    assert tuple(tensor.shape) == (3, 4, 4)
    assert float(tensor.max()) == 0.0


def test_resolve_device_accepts_an_explicit_value() -> None:
    """A configured device name is used as is."""
    assert resolve_device("cpu").type == "cpu"


def test_resolve_device_auto_returns_a_real_device() -> None:
    """Auto picks MPS, CUDA or CPU, never an invalid value."""
    assert resolve_device(AUTO_DEVICE).type in {"mps", "cuda", "cpu"}
