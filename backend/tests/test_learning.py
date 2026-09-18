from app.learning.models import VersionStatus
from app.learning.versioning import ModelVersionRegistry, PromotionPolicy
from app.learning.weights import AdaptiveWeightLearner, FactorObservation, WeightLearningConfig


def observations(factor: str, count: int, hit: bool) -> list[FactorObservation]:
    return [
        FactorObservation(
            factor=factor,
            factor_score=50,
            outcome_return_pct=1 if hit else -1,
            regime="BULL",
        )
        for _ in range(count)
    ]


def test_adaptive_weights_change_only_when_sample_is_sufficient() -> None:
    current = {"trend": 0.5, "momentum": 0.5}
    learner = AdaptiveWeightLearner(WeightLearningConfig(min_observations_per_factor=5))
    candidate = learner.propose_weights(
        current,
        observations("trend", 5, True) + observations("momentum", 5, False),
    )

    assert sum(candidate.values()) == 1.0
    assert candidate["trend"] > current["trend"]
    assert candidate["momentum"] < current["momentum"]


def test_insufficient_factor_data_preserves_that_weight_before_normalization() -> None:
    current = {"trend": 0.6, "momentum": 0.4}
    learner = AdaptiveWeightLearner(WeightLearningConfig(min_observations_per_factor=5))
    candidate = learner.propose_weights(current, observations("trend", 4, True))

    assert candidate == current


def test_version_must_be_validated_before_activation() -> None:
    registry = ModelVersionRegistry()
    version = registry.register_candidate(
        "factor-model",
        {"trend": 0.5, "momentum": 0.5},
        training_observations=200,
        oos_observations=120,
        validation_metrics={"oos_expectancy_pct": 0.2},
    )

    try:
        registry.activate(version.version_id)
        assert False, "activation should require validation"
    except ValueError:
        pass

    validated = registry.mark_validated(version.version_id)
    assert validated.status == VersionStatus.VALIDATED
    active = registry.activate(version.version_id)
    assert active.status == VersionStatus.ACTIVE
    assert registry.active("factor-model").version_id == version.version_id


def test_promotion_policy_is_separate_from_activation() -> None:
    registry = ModelVersionRegistry()
    version = registry.register_candidate(
        "factor-model",
        {"trend": 0.5, "momentum": 0.5},
        training_observations=200,
        oos_observations=120,
        validation_metrics={"oos_expectancy_pct": 0.2},
    )
    assert PromotionPolicy(100, 0.1).qualifies(version) is True
    assert registry.active("factor-model") is None
