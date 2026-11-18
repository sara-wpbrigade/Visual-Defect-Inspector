"""Persona configuration: what is inspected and how results map to actions."""

import re
from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas import DEFECT_SEVERITIES, Action, Severity

CONFIG_DIR = Path(__file__).resolve().parents[2] / "config" / "personas"
PERSONA_NAME_PATTERN = re.compile(r"[a-z][a-z_]{0,40}")


class SeverityBands(BaseModel):
    """Upper limits of the flagged-area ratio for the low and medium bands."""

    low_max: float = Field(gt=0, lt=1)
    medium_max: float = Field(gt=0, lt=1)

    @model_validator(mode="after")
    def check_order(self) -> Self:
        """Reject bands whose limits are not increasing."""
        if self.low_max >= self.medium_max:
            raise ValueError("low_max must be smaller than medium_max")
        return self


class PersonaReport(BaseModel):
    """How a report should read for this persona."""

    audience: str = Field(min_length=1)
    tone: str = Field(min_length=1)
    language: str = Field(min_length=1)


class PersonaConfig(BaseModel):
    """Everything that makes one user type behave differently from another."""

    name: str
    defect_types: list[str] = Field(min_length=1)
    decision_cutoff: float = Field(gt=0, lt=1)
    review_margin: float = Field(ge=0, lt=0.5)
    severity_bands: SeverityBands
    on_pass: Action
    on_uncertain: Action
    on_defect: dict[Severity, Action]
    report: PersonaReport
    action_text: dict[Action, str]

    @field_validator("on_defect")
    @classmethod
    def check_all_severities(cls, value: dict[Severity, Action]) -> dict[Severity, Action]:
        """Require an action for every defect severity."""
        missing = set(DEFECT_SEVERITIES) - set(value)
        if missing:
            raise ValueError(f"on_defect is missing: {sorted(missing)}")
        return value

    @field_validator("action_text")
    @classmethod
    def check_all_actions(cls, value: dict[Action, str]) -> dict[Action, str]:
        """Require one non-empty sentence for every action."""
        missing = set(Action) - set(value)
        if missing:
            raise ValueError(f"action_text is missing: {sorted(missing)}")
        if any(not sentence.strip() for sentence in value.values()):
            raise ValueError("action_text sentences must not be empty")
        return value


def load_persona(name: str, config_dir: Path = CONFIG_DIR) -> PersonaConfig:
    """Load and validate a persona config by name."""
    if not PERSONA_NAME_PATTERN.fullmatch(name):
        raise ValueError(f"Invalid persona name: {name!r}")
    return PersonaConfig.model_validate_json((config_dir / f"{name}.json").read_text())
