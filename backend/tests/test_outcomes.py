from datetime import datetime, timedelta, timezone

from app.backtest.outcomes import label_outcome
from app.models.market import OHLCVBar


def make_bars(closes: list[float]) -> list[OHLCVBar]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        OHLCVBar(
            timestamp=start + timedelta(hours=index),
            open=close,
            high=close * 1.01,
            low=close * 0.99,
            close=close,
            volume=100,
        )
        for index, close in enumerate(closes)
    ]


def test_outcome_uses_next_bar_open_and_future_close() -> None:
    result = label_outcome(make_bars([100, 105, 110, 120]), 0, 2)

    assert result.entry_price == 105
    assert result.forward_return_pct == (120 / 105 - 1) * 100
    assert result.label == "POSITIVE"


def test_outcome_does_not_invent_missing_future_data() -> None:
    result = label_outcome(make_bars([100, 101]), 0, 2)

    assert result.forward_return_pct is None
    assert result.label == "INSUFFICIENT_FUTURE_DATA"
