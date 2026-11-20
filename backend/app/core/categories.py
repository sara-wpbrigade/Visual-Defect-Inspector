"""Category configuration loader.

Scans *backend/config/categories/*.json*, validates each file, and builds a
read‑only ``CategoryCatalog`` that contains only categories whose checkpoint **and**
prototype files exist **inside the backend directory**.

All helper functions are ≤ 30 lines and every line ≤ 100 characters.  The
module uses only the standard library.
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from types import MappingProxyType

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Immutable data model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class CategoryConfig:
    """Immutable configuration for a single MVTec category."""

    id: str
    display_name: str
    description: str
    checkpoint_path: pathlib.Path
    prototype_path: pathlib.Path
    min_similarity: float
    defect_types: tuple[str, ...]  # immutable sequence
    severity_bands: MappingProxyType  # immutable mapping


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
_BACKEND_ROOT = pathlib.Path(__file__).resolve().parents[2]  # backend/


# --------------------------------------------------------------------------- #
# Small validation helpers (each < 30 lines)
# --------------------------------------------------------------------------- #
def _load_json(file_path: pathlib.Path) -> dict:
    """Read JSON and ensure the top‑level object is a mapping."""
    try:
        data = json.loads(file_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {file_path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object in {file_path.name}")
    return data


def _ensure_inside_backend(path: pathlib.Path, ctx: str) -> pathlib.Path:
    """Return the absolute path and guarantee it stays inside the backend dir."""
    resolved = path.resolve()
    if not resolved.is_relative_to(_BACKEND_ROOT):
        raise ValueError(f"{ctx} {resolved} resolves outside the backend directory.")
    return resolved


def _validate_id(cat_id: str, filename: str) -> None:
    """Validate the ID format and that it matches the filename."""
    if not isinstance(cat_id, str):
        raise ValueError(f"'id' must be a string in {filename}.")
    if not _ID_PATTERN.fullmatch(cat_id):
        raise ValueError(
            f"Invalid category id '{cat_id}' in {filename}; must match `^[a-z][a-z0-9_]{{0,40}}$`."
        )
    expected = filename.removesuffix(".json")
    if cat_id != expected:
        raise ValueError(f"Category id '{cat_id}' does not match file name '{filename}'.")


def _validate_numeric(value, name: str, filename: str) -> float:
    """Accept int/float but reject booleans; return a float."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"'{name}' must be numeric (not boolean) in {filename}.")
    return float(value)


def _validate_defect_types(types, filename: str) -> tuple[str, ...]:
    """Non‑empty list of unique, non‑empty strings."""
    if not isinstance(types, list) or not types:
        raise ValueError(f"'defect_types' must be a non‑empty list in {filename}.")
    cleaned: list[str] = []
    for i, t in enumerate(types):
        if not isinstance(t, str) or not t.strip():
            raise ValueError(f"'defect_types[{i}]' must be a non‑empty string in {filename}.")
        cleaned.append(t.strip())
    if len(set(cleaned)) != len(cleaned):
        raise ValueError(f"'defect_types' contains duplicate entries in {filename}.")
    return tuple(cleaned)


def _validate_severity_bands(bands, filename: str) -> MappingProxyType:
    """Require exactly ``low_max`` and ``medium_max`` with 0 < low < medium < 1."""
    if not isinstance(bands, dict):
        raise ValueError(f"'severity_bands' must be an object in {filename}.")
    required = {"low_max", "medium_max"}
    if set(bands) != required:
        raise ValueError(
            f"'severity_bands' must contain exactly low_max and medium_max in {filename}."
        )
    low = _validate_numeric(bands["low_max"], "low_max", filename)
    med = _validate_numeric(bands["medium_max"], "medium_max", filename)
    if not (0 < low < med < 1):
        raise ValueError(
            f"'severity_bands' must satisfy 0 < low_max < medium_max < 1 in {filename}."
        )
    return MappingProxyType({"low_max": low, "medium_max": med})


def _resolve_relative_path(raw_path: str, field_name: str, filename: str) -> pathlib.Path:
    """Validate that a path is relative, reject absolute values, and keep it inside backend."""
    if not isinstance(raw_path, str):
        raise ValueError(f"'{field_name}' must be a string in {filename}.")
    if pathlib.Path(raw_path).is_absolute():
        raise ValueError(f"'{field_name}' must be relative, not absolute, in {filename}.")
    candidate = _BACKEND_ROOT / raw_path
    return _ensure_inside_backend(candidate, field_name)


def _assemble_config(raw: dict, filename: str) -> CategoryConfig:
    """Create a fully‑validated ``CategoryConfig`` from a JSON dict."""
    # id
    cat_id = raw.get("id")
    if cat_id is None:
        raise ValueError(f"'id' is required in {filename}.")
    _validate_id(cat_id, filename)

    # required string fields
    for key in ("display_name", "description", "checkpoint_path", "prototype_path"):
        if not isinstance(raw.get(key), str):
            raise ValueError(f"'{key}' must be a string in {filename}.")

    # numeric gate
    min_sim = _validate_numeric(raw.get("min_similarity"), "min_similarity", filename)
    if not (0.0 <= min_sim <= 1.0):
        raise ValueError(f"'min_similarity' must be between 0 and 1 in {filename}.")

    # defect types
    defect_types = _validate_defect_types(raw.get("defect_types"), filename)

    # severity bands
    severity = _validate_severity_bands(raw.get("severity_bands"), filename)

    # resolve checkpoint / prototype (must be relative to backend)
    chk_path = _resolve_relative_path(raw["checkpoint_path"], "checkpoint_path", filename)
    proto_path = _resolve_relative_path(raw["prototype_path"], "prototype_path", filename)

    return CategoryConfig(
        id=raw["id"],
        display_name=raw["display_name"],
        description=raw["description"],
        checkpoint_path=chk_path,
        prototype_path=proto_path,
        min_similarity=min_sim,
        defect_types=defect_types,
        severity_bands=severity,
    )


# --------------------------------------------------------------------------- #
# Public loaders
# --------------------------------------------------------------------------- #
def _default_categories_dir() -> pathlib.Path:
    """Return the shipped category configuration directory."""
    return _BACKEND_ROOT / "config" / "categories"


def _scan_configs(dir_path: pathlib.Path) -> list[CategoryConfig]:
    """Read and validate every JSON file in *dir_path*."""
    if not dir_path.is_dir():
        raise FileNotFoundError(f"Category config directory not found: {dir_path}")
    if not dir_path.resolve().is_relative_to(_BACKEND_ROOT):
        raise ValueError(f"Custom categories directory {dir_path} must be inside the backend tree.")
    json_files = sorted(dir_path.glob("*.json"))
    if not json_files:
        raise RuntimeError(f"No JSON configuration files found in {dir_path}")

    raw_files = [(file_path, _load_json(file_path)) for file_path in json_files]
    _check_duplicate_ids(raw_files)
    return [_assemble_config(raw, file_path.name) for file_path, raw in raw_files]


def _check_duplicate_ids(raw_files: list[tuple[pathlib.Path, dict]]) -> None:
    """Reject two files that claim the same category id."""
    seen: set[str] = set()
    for file_path, raw in raw_files:
        category_id = raw.get("id")
        if not isinstance(category_id, str):
            continue
        if category_id in seen:
            raise ValueError(f"Duplicate category id '{category_id}' in {file_path.name}")
        seen.add(category_id)


def _missing_files(config: CategoryConfig) -> list[str]:
    """Return the configured files that do not exist yet."""
    missing: list[str] = []
    for label, path in (
        ("checkpoint", config.checkpoint_path),
        ("prototype", config.prototype_path),
    ):
        if not path.is_file():
            missing.append(f"{label} ({path.relative_to(_BACKEND_ROOT)})")
    return missing


def load_categories(
    dir_path: pathlib.Path | None = None,
    enabled: Iterable[str] | None = None,
) -> CategoryCatalog:
    """Load the category JSON files and return the catalog of available categories.

    A category is available only when both its checkpoint and prototype files
    exist. Missing files log a warning and are skipped, so adding a config
    before training never breaks start-up.

    Args:
        dir_path: Directory of JSON files; defaults to ``config/categories``.
        enabled: Optional ids to keep; ``None`` or empty keeps every category.

    Raises:
        FileNotFoundError: The directory does not exist.
        RuntimeError: The directory contains no ``*.json`` files.
        ValueError: A file is invalid, duplicated, or escapes the backend tree.
    """
    configs = _scan_configs(dir_path or _default_categories_dir())
    allowed = set(enabled) if enabled else None
    available: list[CategoryConfig] = []
    for config in configs:
        if allowed is not None and config.id not in allowed:
            continue
        missing = _missing_files(config)
        if missing:
            logger.warning(
                "Skipping category %s because %s are missing.",
                config.id,
                " and ".join(missing),
            )
            continue
        available.append(config)
    return CategoryCatalog(available)


def load_category_config(
    category_id: str,
    dir_path: pathlib.Path | None = None,
) -> CategoryConfig:
    """Return one category config even when its model files are not built yet.

    Scripts use this to find where a prototype must be written before the
    category becomes available to the application.

    Raises:
        ValueError: The id does not match any configured category.
    """
    for config in _scan_configs(dir_path or _default_categories_dir()):
        if config.id == category_id:
            return config
    raise ValueError(f"Category '{category_id}' is not configured.")


# --------------------------------------------------------------------------- #
# Catalog – immutable, read‑only view used throughout the codebase
# --------------------------------------------------------------------------- #
class CategoryCatalog:
    """Read‑only collection of available ``CategoryConfig`` objects."""

    def __init__(self, configs: Iterable[CategoryConfig]):
        """Initialize the catalog with available category configurations."""
        self._by_id: dict[str, CategoryConfig] = {c.id: c for c in configs}

    def get(self, id: str) -> CategoryConfig:
        """Return the config for *id* or raise ``KeyError``."""
        return self._by_id[id]

    def ids(self) -> list[str]:
        """All available category identifiers."""
        return list(self._by_id.keys())

    def all(self) -> list[CategoryConfig]:
        """All available ``CategoryConfig`` objects."""
        return list(self._by_id.values())
