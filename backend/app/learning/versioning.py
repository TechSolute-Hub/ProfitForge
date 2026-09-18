from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone

from app.learning.models import ModelVersion, VersionStatus


class ModelVersionRegistry:
    """In-process registry for immutable candidate/active model versions."""

    def __init__(self) -> None:
        self._versions: dict[str, ModelVersion] = {}
        self._active_by_family: dict[str, str] = {}

    @staticmethod
    def checksum(weights: dict[str, float]) -> str:
        payload = json.dumps(weights, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def register_candidate(
        self,
        model_family: str,
        weights: dict[str, float],
        training_observations: int,
        oos_observations: int,
        validation_metrics: dict[str, float],
        parent_version_id: str | None = None,
        version_id: str | None = None,
    ) -> ModelVersion:
        if not model_family.strip():
            raise ValueError("model_family cannot be empty")
        if not weights or any(value <= 0 for value in weights.values()):
            raise ValueError("weights must be positive")
        if training_observations < 0 or oos_observations < 0:
            raise ValueError("observation counts cannot be negative")
        if version_id is None:
            version_id = f"{model_family}-{len(self._versions) + 1:06d}"
        if version_id in self._versions:
            raise ValueError(f"version {version_id!r} already exists")

        candidate = ModelVersion(
            version_id=version_id,
            model_family=model_family,
            created_at=datetime.now(timezone.utc),
            status=VersionStatus.DRAFT,
            weights=dict(weights),
            parent_version_id=parent_version_id,
            training_observations=training_observations,
            oos_observations=oos_observations,
            validation_metrics=dict(validation_metrics),
            artifact_checksum=self.checksum(weights),
        )
        self._versions[version_id] = candidate
        return candidate

    def mark_validated(self, version_id: str) -> ModelVersion:
        version = self._require(version_id)
        if version.status not in (VersionStatus.DRAFT, VersionStatus.VALIDATED):
            raise ValueError("only draft versions can be validated")
        updated = replace(version, status=VersionStatus.VALIDATED)
        self._versions[version_id] = updated
        return updated

    def activate(self, version_id: str) -> ModelVersion:
        """Explicitly activate a validated version; never automatic promotion."""

        version = self._require(version_id)
        if version.status != VersionStatus.VALIDATED:
            raise ValueError("only validated versions can be activated")
        current_id = self._active_by_family.get(version.model_family)
        if current_id:
            current = self._versions[current_id]
            self._versions[current_id] = replace(current, status=VersionStatus.ROLLED_BACK)
        updated = replace(version, status=VersionStatus.ACTIVE)
        self._versions[version_id] = updated
        self._active_by_family[version.model_family] = version_id
        return updated

    def active(self, model_family: str) -> ModelVersion | None:
        version_id = self._active_by_family.get(model_family)
        return self._versions.get(version_id) if version_id else None

    def get(self, version_id: str) -> ModelVersion:
        return self._require(version_id)

    def all_versions(self, model_family: str | None = None) -> list[ModelVersion]:
        values = list(self._versions.values())
        if model_family is not None:
            values = [item for item in values if item.model_family == model_family]
        return sorted(values, key=lambda item: item.created_at)

    def _require(self, version_id: str) -> ModelVersion:
        try:
            return self._versions[version_id]
        except KeyError as exc:
            raise KeyError(f"unknown model version {version_id!r}") from exc


class PromotionPolicy:
    """Validation gate for candidate versions; activation remains explicit."""

    def __init__(self, min_oos_observations: int = 100, min_oos_expectancy_pct: float = 0.0) -> None:
        if min_oos_observations < 1:
            raise ValueError("min_oos_observations must be positive")
        self.min_oos_observations = min_oos_observations
        self.min_oos_expectancy_pct = min_oos_expectancy_pct

    def qualifies(self, version: ModelVersion) -> bool:
        expectancy = version.validation_metrics.get("oos_expectancy_pct")
        return (
            version.oos_observations >= self.min_oos_observations
            and expectancy is not None
            and expectancy >= self.min_oos_expectancy_pct
        )
