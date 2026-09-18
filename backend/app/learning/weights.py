from __future__ import annotations

from dataclasses import dataclass
from math import copysign


@dataclass(frozen=True)
class WeightLearningConfig:
    min_observations_per_factor: int = 30
    learning_rate: float = 0.10
    min_weight: float = 0.05
    max_weight: float = 0.50

    def __post_init__(self) -> None:
        if self.min_observations_per_factor < 1:
            raise ValueError("min_observations_per_factor must be positive")
        if not 0 < self.learning_rate <= 1:
            raise ValueError("learning_rate must be in (0, 1]")
        if not 0 < self.min_weight <= self.max_weight:
            raise ValueError("weight bounds are invalid")
        if self.max_weight > 1:
            raise ValueError("max_weight cannot exceed 1")


@dataclass(frozen=True)
class FactorObservation:
    factor: str
    factor_score: float
    outcome_return_pct: float
    regime: str
    feedback: int = 0

    def __post_init__(self) -> None:
        if self.feedback not in (-1, 0, 1):
            raise ValueError("feedback must be -1, 0 or 1")


class AdaptiveWeightLearner:
    """Create candidate factor weights from validated historical outcomes.

    This learner is intentionally limited to research-factor weights. It cannot
    modify risk limits, position sizing, execution settings or safety controls.
    Candidate weights are returned for versioning and validation; promotion is a
    separate explicit operation.
    """

    def __init__(self, config: WeightLearningConfig | None = None) -> None:
        self.config = config or WeightLearningConfig()

    @staticmethod
    def _direction(value: float) -> int:
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0

    def _factor_hit_rate(self, observations: list[FactorObservation]) -> float | None:
        usable = [item for item in observations if self._direction(item.factor_score)]
        if len(usable) < self.config.min_observations_per_factor:
            return None
        hits = 0.0
        for item in usable:
            prediction = self._direction(item.factor_score)
            outcome = self._direction(item.outcome_return_pct)
            if outcome == 0:
                hits += 0.5
            elif prediction == outcome:
                hits += 1.0
            if item.feedback:
                hits += 0.25 * item.feedback
        return max(0.0, min(1.0, hits / len(usable)))

    def propose_weights(
        self,
        current_weights: dict[str, float],
        observations: list[FactorObservation],
        regime: str | None = None,
    ) -> dict[str, float]:
        """Return normalized candidate weights without changing safety settings."""

        if not current_weights:
            raise ValueError("current_weights cannot be empty")
        if any(value <= 0 for value in current_weights.values()):
            raise ValueError("weights must be positive")
        if abs(sum(current_weights.values()) - 1.0) > 1e-6:
            raise ValueError("current_weights must sum to 1")

        scoped = [item for item in observations if regime is None or item.regime == regime]
        proposed = dict(current_weights)
        for factor in current_weights:
            factor_observations = [item for item in scoped if item.factor == factor]
            hit_rate = self._factor_hit_rate(factor_observations)
            if hit_rate is None:
                continue
            edge = 2 * (hit_rate - 0.5)
            proposed[factor] *= 1 + self.config.learning_rate * edge

        proposed = {
            key: min(self.config.max_weight, max(self.config.min_weight, value))
            for key, value in proposed.items()
        }
        total = sum(proposed.values())
        return {key: value / total for key, value in proposed.items()}
