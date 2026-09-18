from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class VersionStatus(str, Enum):
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    ACTIVE = "ACTIVE"
    ROLLED_BACK = "ROLLED_BACK"


@dataclass(frozen=True)
class ModelVersion:
    version_id: str
    model_family: str
    created_at: datetime
    status: VersionStatus
    weights: dict[str, float]
    parent_version_id: str | None
    training_observations: int
    oos_observations: int
    validation_metrics: dict[str, float]
    artifact_checksum: str
