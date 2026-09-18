from datetime import datetime, timedelta, timezone

import pytest

from app.backtest.validation import ValidationConfig, build_windows, walk_forward_validate
from app.models.market import OHLCVBar


def make_bars(count: int) -> list[OHLCVBar]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        OHLCVBar(
            timestamp=start + timedelta(hours=index),
            open=100 + index,
            high=101 + index,
            low=99 + index,
            close=100 + index,
            volume=1000,
        )
        for index in range(count)
    ]


def test_build_windows_are_chronological_and_purged() -> None:
    windows = build_windows(
        30,
        ValidationConfig(train_bars=10, test_bars=5, step_bars=5, purge_bars=2),
    )

    assert windows[0].train_start == 0
    assert windows[0].train_end == 10
    assert windows[0].test_start == 12
    assert windows[0].test_end == 17
    assert windows[1].train_start == 5
    assert windows[1].test_start == 17


def test_walk_forward_reports_train_and_oos_metrics() -> None:
    bars = make_bars(20)
    scores = [80] * 20
    results = walk_forward_validate(
        bars,
        scores,
        ValidationConfig(train_bars=10, test_bars=5, step_bars=5, min_trades=1),
    )

    assert len(results) == 2
    assert results[0].window.test_start == 10
    assert results[0].test_metrics.trade_count >= 1
    assert results[0].test_metrics.sufficient_sample is True


def test_walk_forward_rejects_non_chronological_data() -> None:
    bars = make_bars(20)
    bars[5] = bars[4]

    with pytest.raises(ValueError, match="strictly chronological"):
        walk_forward_validate(bars, [0] * 20, ValidationConfig(train_bars=10, test_bars=5))


def test_walk_forward_requires_aligned_scores() -> None:
    with pytest.raises(ValueError, match="same length"):
        walk_forward_validate(make_bars(20), [0] * 19, ValidationConfig(train_bars=10, test_bars=5))
