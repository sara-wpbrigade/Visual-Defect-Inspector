"""Tests for the inspection artifact store."""

from pathlib import Path

import pytest
from PIL import Image

from app.services.storage import (
    ARTIFACT_NAMES,
    OVERLAY_KIND,
    PHOTO_KIND,
    THUMBNAIL_KIND,
    ArtifactStore,
    InvalidInspectionIdError,
    StorageError,
    new_inspection_id,
    validate_inspection_id,
)

INSPECTION_ID = "0123456789abcdef0123456789abcdef"
INVALID_IDS = ("../x", INSPECTION_ID.upper(), "a" * 31, "a" * 33, "", "g" * 32)


@pytest.fixture
def store(tmp_path: Path) -> ArtifactStore:
    """Return a store over the test's temporary upload folder."""
    return ArtifactStore(tmp_path)


def test_valid_id_is_accepted() -> None:
    """A 32-character lowercase hex id passes the check."""
    assert validate_inspection_id(INSPECTION_ID) == INSPECTION_ID


def test_new_id_is_always_valid() -> None:
    """The random id generator produces ids that pass the check."""
    for _ in range(5):
        validate_inspection_id(new_inspection_id())


@pytest.mark.parametrize("inspection_id", INVALID_IDS)
def test_unsafe_ids_are_rejected(store: ArtifactStore, inspection_id: str) -> None:
    """Ids that could escape the folder never reach a path."""
    with pytest.raises(InvalidInspectionIdError):
        store.path_for(inspection_id, PHOTO_KIND)


def test_paths_use_fixed_names_derived_from_the_id(store: ArtifactStore, tmp_path: Path) -> None:
    """Each kind maps to one fixed file name in the upload folder."""
    expected = {
        PHOTO_KIND: f"{INSPECTION_ID}.png",
        OVERLAY_KIND: f"{INSPECTION_ID}_overlay.png",
        THUMBNAIL_KIND: f"{INSPECTION_ID}_thumb.jpg",
    }
    for kind, name in expected.items():
        assert store.path_for(INSPECTION_ID, kind) == tmp_path / name
        assert ARTIFACT_NAMES[kind].format(inspection_id=INSPECTION_ID) == name


def test_save_writes_the_fixed_file_names(store: ArtifactStore, tmp_path: Path) -> None:
    """Saving each artifact creates exactly the documented file."""
    image = Image.new("RGB", (8, 8), (10, 20, 30))
    for kind in (PHOTO_KIND, OVERLAY_KIND, THUMBNAIL_KIND):
        path = store.save(image, INSPECTION_ID, kind)
        assert path.is_file()
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        f"{INSPECTION_ID}.png",
        f"{INSPECTION_ID}_overlay.png",
        f"{INSPECTION_ID}_thumb.jpg",
    ]


def test_unknown_kind_is_rejected(store: ArtifactStore) -> None:
    """A kind outside the fixed set is a domain error, not a file name."""
    with pytest.raises(StorageError):
        store.path_for(INSPECTION_ID, "secret")


def test_saved_thumbnail_is_a_jpeg(store: ArtifactStore, tmp_path: Path) -> None:
    """The thumbnail file is written as JPEG bytes."""
    store.save(Image.new("RGB", (8, 8)), INSPECTION_ID, THUMBNAIL_KIND)
    data = (tmp_path / f"{INSPECTION_ID}_thumb.jpg").read_bytes()
    assert data[:2] == b"\xff\xd8"


def test_id_rejection_is_a_storage_error() -> None:
    """The specific id error is part of the storage error family."""
    assert issubclass(InvalidInspectionIdError, StorageError)


def test_store_creates_its_directory(tmp_path: Path) -> None:
    """Saving into a missing folder creates it."""
    store = ArtifactStore(tmp_path / "nested" / "uploads")
    store.save(Image.new("RGB", (4, 4)), INSPECTION_ID, PHOTO_KIND)
    assert (tmp_path / "nested" / "uploads" / f"{INSPECTION_ID}.png").is_file()
