from app.analysis.scoring import WEIGHTS, aggregate_score
from app.analysis.scoring import FactorAssessment


def test_custom_weights_are_used_and_normalized() -> None:
    factors = {
        name: FactorAssessment(100.0 if name == "htf_trend" else 0.0, weight, True, "")
        for name, weight in {"htf_trend": 0.8, "momentum": 0.05, "volume_confirmation": 0.05, "market_structure": 0.05, "news_sentiment": 0.05}.items()
    }
    score, _, available = aggregate_score(factors)

    assert score == 80
    assert available == 1.0
    assert sum(WEIGHTS.values()) == 1.0
