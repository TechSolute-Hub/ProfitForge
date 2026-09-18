from datetime import datetime, timezone

from app.learning.models import ModelVersion, VersionStatus
from app.learning.service import DEFAULT_WEIGHTS
from app.learning.validation import SignalOutcomeObservation


def test_default_weights_are_research_only() -> None:
    assert set(DEFAULT_WEIGHTS) == {
        "htf_trend",
        "momentum",
        "volume_confirmation",
        "market_structure",
        "news_sentiment",
    }


def test_model_version_uses_enum_status() -> None:
    version = ModelVersion(
        version_id="research-factor-v1-test",
        model_family="research-factor-v1",
        created_at=datetime.now(timezone.utc),
        status=VersionStatus.DRAFT,
        weights=DEFAULT_WEIGHTS,
        parent_version_id=None,
        training_observations=100,
        oos_observations=0,
        validation_metrics={},
        artifact_checksum="x",
    )
    assert version.status == VersionStatus.DRAFT


def test_holdout_is_strictly_after_training_records() -> None:
    records = [
        SignalOutcomeObservation(
            str(index),
            f"2026-01-{index + 1:02d}T00:00:00+00:00",
            {"htf_trend": 80, "momentum": -20},
            1.0 if index < 100 else -1.0,
            "BULL",
        )
        for index in range(110)
    ]
    train = records[:-22]
    holdout = records[-22:]
    assert train[-1].signal_time < holdout[0].signal_time
    assert holdout[-1].outcome_return_pct == -1.0
