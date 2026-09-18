from __future__ import annotations

from dataclasses import dataclass

from app.learning.weights import AdaptiveWeightLearner, FactorObservation


@dataclass(frozen=True)
class SignalOutcomeObservation:
    signal_id: str
    signal_time: str
    factor_scores: dict[str, float]
    outcome_return_pct: float
    regime: str


@dataclass(frozen=True)
class WalkForwardWeightResult:
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    train_observations: int
    oos_observations: int
    train_expectancy_pct: float
    oos_expectancy_pct: float
    oos_hit_rate_pct: float


def _factor_observations(records: list[SignalOutcomeObservation]) -> list[FactorObservation]:
    return [FactorObservation(factor, score, record.outcome_return_pct, record.regime) for record in records for factor, score in record.factor_scores.items()]


def evaluate_weights(records: list[SignalOutcomeObservation], weights: dict[str, float]) -> tuple[float, float]:
    returns: list[float] = []
    hits = 0
    for record in records:
        score = sum(record.factor_scores.get(factor, 0.0) * weight for factor, weight in weights.items())
        if score == 0:
            continue
        signed_return = (1 if score > 0 else -1) * record.outcome_return_pct
        returns.append(signed_return)
        hits += int(signed_return > 0)
    return (sum(returns) / len(returns) if returns else 0.0, hits / len(returns) * 100 if returns else 0.0)


def walk_forward_weight_validation(records: list[SignalOutcomeObservation], learner: AdaptiveWeightLearner, current_weights: dict[str, float], train_size: int = 100, test_size: int = 25, step_size: int = 25) -> list[WalkForwardWeightResult]:
    if train_size < 2 or test_size < 1 or step_size < 1:
        raise ValueError("walk-forward sizes must be positive")
    ordered = sorted(records, key=lambda item: item.signal_time)
    results: list[WalkForwardWeightResult] = []
    start = 0
    while start + train_size + test_size <= len(ordered):
        train = ordered[start:start + train_size]
        test = ordered[start + train_size:start + train_size + test_size]
        candidate = learner.propose_weights(current_weights, _factor_observations(train))
        train_expectancy, _ = evaluate_weights(train, candidate)
        oos_expectancy, oos_hit_rate = evaluate_weights(test, candidate)
        results.append(WalkForwardWeightResult(start, start + train_size, start + train_size, start + train_size + test_size, len(train), len(test), train_expectancy, oos_expectancy, oos_hit_rate))
        start += step_size
    return results
