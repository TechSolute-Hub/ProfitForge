from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import Settings
from app.learning.models import ModelVersion, VersionStatus
from app.learning.persistence import ModelPersistenceError, SupabaseModelRepository
from app.learning.validation import (
    evaluate_weight_set,
    walk_forward_weight_validation,
)
from app.learning.versioning import PromotionPolicy
from app.learning.weights import (
    AdaptiveWeightLearner,
    FactorObservation,
    WeightLearningConfig,
)

DEFAULT_WEIGHTS = {
    "htf_trend": 0.25,
    "momentum": 0.25,
    "volume_confirmation": 0.15,
    "market_structure": 0.20,
    "news_sentiment": 0.15,
}
MIN_LEARNING_OBSERVATIONS = 100
MIN_HOLDOUT_OBSERVATIONS = 25
MIN_PROMOTION_OOS_OBSERVATIONS = 50
MAX_BASELINE_DEGRADATION_PCT = 0.25


class LearningService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.repository = SupabaseModelRepository(settings)
        self.learner = AdaptiveWeightLearner(WeightLearningConfig())

    async def active_weights(self) -> tuple[dict[str, float], str | None]:
        try:
            active = await self.repository.active_model(self.settings.model_family)
        except ModelPersistenceError:
            return dict(DEFAULT_WEIGHTS), None
        if active is None:
            return dict(DEFAULT_WEIGHTS), None
        return dict(active.weights), active.version_id

    async def learn_candidate(self) -> ModelVersion:
        records = await self.repository.signal_outcomes()
        if len(records) < MIN_LEARNING_OBSERVATIONS:
            raise ModelPersistenceError(
                f"At least {MIN_LEARNING_OBSERVATIONS} verified outcomes are required"
            )

        active = await self.repository.active_model(self.settings.model_family)
        current = active.weights if active else DEFAULT_WEIGHTS
        train = records[: int(len(records) * 0.8)]
        observations = [
            FactorObservation(
                factor,
                score,
                record.outcome_return_pct,
                record.regime,
            )
            for record in train
            for factor, score in record.factor_scores.items()
        ]
        candidate_weights = self.learner.propose_weights(
            current,
            observations,
        )
        version = ModelVersion(
            version_id=f"{self.settings.model_family}-{uuid4().hex[:12]}",
            model_family=self.settings.model_family,
            created_at=datetime.now(timezone.utc),
            status=VersionStatus.DRAFT,
            weights=candidate_weights,
            parent_version_id=active.version_id if active else None,
            training_observations=len(train),
            oos_observations=0,
            validation_metrics={},
            artifact_checksum=self._checksum(candidate_weights),
        )
        return await self.repository.create_candidate(version)

    async def validate_candidate(self, version_id: str) -> ModelVersion:
        candidate = await self.repository.get_model(version_id)
        if candidate is None or candidate.status != VersionStatus.DRAFT:
            raise ModelPersistenceError(
                "Only draft candidates can be validated"
            )

        records = await self.repository.signal_outcomes()
        if len(records) < MIN_LEARNING_OBSERVATIONS:
            raise ModelPersistenceError(
                f"At least {MIN_LEARNING_OBSERVATIONS} verified outcomes are required"
            )

        active = await self.repository.active_model(self.settings.model_family)
        baseline = active.weights if active else DEFAULT_WEIGHTS

        split = max(
            MIN_HOLDOUT_OBSERVATIONS,
            int(len(records) * 0.20),
        )
        if len(records) - split < 50:
            split = max(MIN_HOLDOUT_OBSERVATIONS, len(records) // 5)
        train = records[:-split]
        holdout = records[-split:]
        if len(train) < MIN_LEARNING_OBSERVATIONS:
            raise ModelPersistenceError(
                "Insufficient pre-holdout observations for validation"
            )

        train_size = min(100, max(20, len(train) // 2))
        test_size = min(25, max(10, len(train) // 5))
        step_size = max(10, min(25, len(train) // 5))
        windows = walk_forward_weight_validation(
            train,
            self.learner,
            baseline,
            train_size=train_size,
            test_size=test_size,
            step_size=step_size,
        )
        if not windows:
            raise ModelPersistenceError(
                "No complete walk-forward windows are available"
            )

        candidate_holdout = evaluate_weight_set(holdout, candidate.weights)
        baseline_holdout = evaluate_weight_set(holdout, baseline)
        walk_forward_oos = sum(
            window.oos_expectancy_pct for window in windows
        ) / len(windows)
        walk_forward_hit_rate = sum(
            window.oos_hit_rate_pct for window in windows
        ) / len(windows)

        improvement = (
            candidate_holdout.expectancy_pct
            - baseline_holdout.expectancy_pct
        )
        metrics = {
            "oos_expectancy_pct": candidate_holdout.expectancy_pct,
            "walk_forward_windows": float(len(windows)),
            "walk_forward_oos_expectancy_pct": walk_forward_oos,
            "walk_forward_oos_hit_rate_pct": walk_forward_hit_rate,
            "candidate_holdout_expectancy_pct": (
                candidate_holdout.expectancy_pct
            ),
            "candidate_holdout_hit_rate_pct": candidate_holdout.hit_rate_pct,
            "candidate_holdout_observations": float(
                candidate_holdout.observations
            ),
            "baseline_holdout_expectancy_pct": (
                baseline_holdout.expectancy_pct
            ),
            "baseline_holdout_hit_rate_pct": baseline_holdout.hit_rate_pct,
            "holdout_improvement_pct": improvement,
        }

        oos_count = candidate_holdout.observations
        await self.repository.update_validation(
            version_id,
            oos_count,
            metrics,
        )

        validated = ModelVersion(
            version_id=candidate.version_id,
            model_family=candidate.model_family,
            created_at=candidate.created_at,
            status=candidate.status,
            weights=candidate.weights,
            parent_version_id=candidate.parent_version_id,
            training_observations=candidate.training_observations,
            oos_observations=oos_count,
            validation_metrics=metrics,
            artifact_checksum=candidate.artifact_checksum,
        )
        policy = PromotionPolicy(
            min_oos_observations=MIN_PROMOTION_OOS_OBSERVATIONS,
            min_oos_expectancy_pct=0.0,
        )
        if not policy.qualifies(validated):
            raise ModelPersistenceError(
                "Candidate failed minimum OOS promotion criteria"
            )
        if (
            baseline_holdout.observations > 0
            and improvement < -MAX_BASELINE_DEGRADATION_PCT
        ):
            raise ModelPersistenceError(
                "Candidate materially underperforms the active baseline"
            )

        return await self.repository.mark_validated(version_id)

    async def activate(self, version_id: str) -> ModelVersion:
        return await self.repository.activate(version_id)

    @staticmethod
    def _checksum(weights: dict[str, float]) -> str:
        import hashlib
        import json

        payload = json.dumps(
            weights,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
