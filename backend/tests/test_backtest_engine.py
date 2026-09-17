from datetime import datetime, timedelta, timezone

import pytest

from app.backtest.engine import BacktestConfig, run_backtest
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
            volume=1000,
        )
        for index, close in enumerate(closes)
    ]


def test_signal_enters_on_next_bar_not_signal_bar() -> None:
    bars = make_bars([100, 200, 210, 220, 230])
    scores = [80, 0, 0, 0, 0]
    result = run_backtest(
        bars,
        scores,
        BacktestConfig(holding_bars=1, take_profit_pct=0.50, stop_loss_pct=0.50),
    )

    assert result.trade_count == 1
    assert result.trades[0].signal_time == bars[0].timestamp
    assert result.trades[0].entry_time == bars[1].timestamp
    assert result.trades[0].entry_price == pytest.approx(200.0 * 1.0002)


def test_stop_wins_when_stop_and_target_are_both_touched() -> None:
    bars = make_bars([100, 100, 100])
    bars[1] = OHLCVBar(
        timestamp=bars[1].timestamp,
        open=100,
        high=110,
        low=90,
        close=100,
        volume=1000,
    )
    result = run_backtest(
        bars,
        [80, 0, 0],
        BacktestConfig(holding_bars=1, stop_loss_pct=0.05, take_profit_pct=0.05),
    )

    assert result.trade_count == 1
    assert result.trades[0].exit_reason == "STOP"
    assert result.trades[0].net_return_pct < 0


def test_chronology_is_required() -> None:
    bars = make_bars([100, 101, 102])
    bars[1] = bars[0]

    with pytest.raises(ValueError, match="strictly chronological"):
        run_backtest(bars, [0, 0, 0])


def test_lengths_must_match() -> None:
    bars = make_bars([100, 101, 102])

    with pytest.raises(ValueError, match="same length"):
        run_backtest(bars, [0, 0])
