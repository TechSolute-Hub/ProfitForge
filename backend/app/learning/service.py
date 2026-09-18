from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import Settings
from app.learning.models import ModelVersion
from app.learning.persistence import ModelPersistenceError, SupabaseModelRepository
from app.learning.versioning import ModelVersionRegistry, PromotionPolicy
from app.learning.weights import AdaptiveWeightLearner, FactorObservation, WeightLearningConfig

DEFAULT_WEIGHTS = {
    "htf_trend": 0.25,
    "momentum": 0.25,
    "volume_confirmation": 0.15,
    "market_structure": 0.20,
    "news_sentiment": 0.15,
}


class LearningService:
    """Connect outcome history, candidate learning and persistent versions."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.repository = SupabaseModelRepository(settings)
        self.learner = AdaptiveWeightLearner(WeightLearningConfig())
        self.registry = ModelVersionRegistry()

    async def active_weights(self) -> tuple[dict[str, float], str | None]:
        try:
            active = await self.repository.active_model(self.settings.model_family)
        except ModelPersistenceError:
            return dict(DEFAULT_WEIGHTS), None
        if active is None:
            return dict(DEFAULT_WEIGHTS), None
        return dict(active.weights), active.version_id

    async def learn_candidate(self) -> ModelVersion:
        observations = await self.repository.signal_outcomes(limit=5000)
        if len(observations) < 30:
            raise ModelPersistenceError("At least 30 resolved factor observations are required")

        active = await self.repository.active_model(self.settings.model_family)
        current_weights = active.weights if active else DEFAULT_WEIGHTS
        candidate_weights = self.learner.propose_weights(current_weights, observations)
        version = self.registry.register_candidate(
            model_family=self.settings.model_family,
            weights=candidate_weights,
            training_observations=len(observations),
            oos_observations=0,
            validation_metrics={},
            parent_version_id=active.version_id if active else None,
            version_id=f"{self.settings.model_family}-{uuid4().hex[:12]}",
        )
        return await self.repository.create_candidate(version)

    async def validate_candidate(self, version_id: str, policy: PromotionPolicy | None = None) -> ModelVersion:
        policy = policy or PromotionPolicy()
        version = await self.repository.active_model(self.settings.model_family)
        _ = version
        observations = await self.repository.signal_outcomes(limit=5000)
        candidate_rows = await self.repository._request(
            "GET", "model_versions", params={"select":"*", "version_id":f"eq.{version_id}", "limit":"1"}
        )
        if not candidate_rows:
            raise ModelPersistenceError("Candidate model version was not found")
        candidate = self.repository._request
        row = candidate_rows[0]
        model = self.registry.register_candidate(
            model_family=str(row["model_family"]),
            weights={str(k): float(v) for k, v in dict(row["weights"]).items()},
            training_observations=int(row["training_observations"]),
            oos_observations=int(row["oos_observations"]),
            validation_metrics={str(k): float(v) for k, v in dict(row["validation_metrics"]).items()},
            parent_version_id=str(row["parent_version_id"]) if row.get("parent_version_id") else None,
            version_id=str(row["version_id"]),
        )
        # Use a deterministic chronological holdout. The candidate is never fitted on this holdout.
        split = max(1, int(len(observations) * 0.8))
        train = observations[:split]
        test = observations[split:]
        if not test:
            raise ModelPersistenceError("Insufficient observations for OOS validation")
        baseline = self.learner.propose_weights(DEFAULT_WEIGHTS, train)
        oos = _evaluate(test, model.weights)
        train_metrics = _evaluate(train, baseline)
        metrics = {
            "train_expectancy_pct": train_metrics,
            "oos_expectancy_pct": oos,
            "oos_observations": float(len(test)),
        }
        candidate_model = ModelVersion(
            version_id=model.version_id,
            model_family=model.model_family,
            created_at=model.created_at,
            status=model.status,
            weights=model.weights,
            parent_version_id=model.parent_version_id,
            training_observations=model.training_observations,
            oos_observations=len(test),
            validation_metrics=metrics,
            artifact_checksum=model.artifact_checksum,
        )
        await self.repository._request(
            "PATCH", "model_versions", params={"version_id":f"eq.{version_id}"},
            payload={"oos_observations":len(test), "validation_metrics":metrics},
        )
        if not policy.qualifies(candidate_model):
            raise ModelPersistenceError("Candidate failed OOS promotion criteria")
        return await self.repository.mark_validated(version_id)

    async def activate(self, version_id: str) -> ModelVersion:
        return await self.repository.activate(version_id)


def _evaluate(observations: list[FactorObservation], weights: dict[str, float]) -> float:
    returns: list[float] = []
    for observation_group in _group_observations(observations):
        score = sum(item.factor_score * weights.get(item.factor, 0.0) for item in observation_group)
        direction = 1 if score > 0 else -1 if score < 0 else 0
        if direction:
            returns.append(direction * observation_group[0].outcome_return_pct)
    return sum(returns) / len(returns) if returns else 0.0


def _group_observations(observations: list[FactorObservation]) -> list[list[FactorObservation]]:
    grouped: dict[tuple[str, float, str], list[FactorObservation]] = {}
    for item in observations:
        key = (item.regime, item.outcome_return_pct, str(id(item)))
        grouped.setdefault(key, []).append(item)
    return list(grouped.values())
