from app.learning.validation import SignalOutcomeObservation, evaluate_weights, walk_forward_weight_validation
from app.learning.weights import AdaptiveWeightLearner, WeightLearningConfig


def records(count: int) -> list[SignalOutcomeObservation]:
    return [SignalOutcomeObservation(str(i), f"2026-01-{i + 1:02d}T00:00:00+00:00", {"htf_trend": 80, "momentum": 20}, 1.0, "BULL") for i in range(count)]


def test_walk_forward_uses_future_segment_only_for_oos() -> None:
    learner = AdaptiveWeightLearner(WeightLearningConfig(min_observations_per_factor=2))
    result = walk_forward_weight_validation(records(12), learner, {"htf_trend": 0.5, "momentum": 0.5}, train_size=6, test_size=3, step_size=3)

    assert len(result) == 2
    assert result[0].train_end == result[0].test_start
    assert result[0].oos_observations == 3


def test_weight_evaluation_is_directional() -> None:
    expectancy, hit_rate = evaluate_weights(records(4), {"htf_trend": 1.0, "momentum": 0.0})

    assert expectancy == 1.0
    assert hit_rate == 100.0
