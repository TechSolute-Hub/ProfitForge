from __future__ import annotations

from dataclasses import dataclass

from app.backtest.engine import BacktestConfig, BacktestResult, run_backtest
from app.models.market import OHLCVBar


@dataclass(frozen=True)
class ValidationConfig:
    """Rolling walk-forward window configuration."""

    train_bars: int = 500
    test_bars: int = 100
    step_bars: int = 100
    purge_bars: int = 0
    min_trades: int = 5

    def __post_init__(self) -> None:
        if self.train_bars < 2:
            raise ValueError("train_bars must be at least 2")
        if self.test_bars < 2:
            raise ValueError("test_bars must be at least 2")
        if self.step_bars < 1:
            raise ValueError("step_bars must be positive")
        if self.purge_bars < 0:
            raise ValueError("purge_bars cannot be negative")
        if self.min_trades < 0:
            raise ValueError("min_trades cannot be negative")


@dataclass(frozen=True)
class ValidationWindow:
    index: int
    train_start: int
    train_end: int
    test_start: int
    test_end: int

    @property
    def train_size(self) -> int:
        return self.train_end - self.train_start

    @property
    def test_size(self) -> int:
        return self.test_end - self.test_start


@dataclass(frozen=True)
class ValidationMetrics:
    trade_count: int
    win_rate_pct: float
    total_return_pct: float
    max_drawdown_pct: float
    profit_factor: float | None
    expectancy_pct: float
    sufficient_sample: bool


@dataclass(frozen=True)
class WalkForwardResult:
    window: ValidationWindow
    train_metrics: ValidationMetrics
    test_metrics: ValidationMetrics


def build_windows(length: int, config: ValidationConfig | None = None) -> list[ValidationWindow]:
    """Build chronological train/test windows with an optional purge gap."""

    config = config or ValidationConfig()
    if length < config.train_bars + config.purge_bars + config.test_bars:
        return []

    windows: list[ValidationWindow] = []
    start = 0
    index = 0
    while start + config.train_bars + config.purge_bars + config.test_bars <= length:
        train_start = start
        train_end = start + config.train_bars
        test_start = train_end + config.purge_bars
        test_end = test_start + config.test_bars
        windows.append(
            ValidationWindow(
                index=index,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
        )
        index += 1
        start += config.step_bars
    return windows


def _metrics(result: BacktestResult, min_trades: int) -> ValidationMetrics:
    gross_wins = sum(trade.net_return_pct for trade in result.trades if trade.net_return_pct > 0)
    gross_losses = -sum(trade.net_return_pct for trade in result.trades if trade.net_return_pct < 0)
    profit_factor = gross_wins / gross_losses if gross_losses > 0 else None
    expectancy = (
        sum(trade.net_return_pct for trade in result.trades) / result.trade_count
        if result.trade_count
        else 0.0
    )
    return ValidationMetrics(
        trade_count=result.trade_count,
        win_rate_pct=result.win_rate_pct,
        total_return_pct=result.total_return_pct,
        max_drawdown_pct=result.max_drawdown_pct,
        profit_factor=profit_factor,
        expectancy_pct=expectancy,
        sufficient_sample=result.trade_count >= min_trades,
    )


def walk_forward_validate(
    bars: list[OHLCVBar],
    scores: list[int],
    validation_config: ValidationConfig | None = None,
    backtest_config: BacktestConfig | None = None,
) -> list[WalkForwardResult]:
    """Evaluate fixed point-in-time scores on rolling train/test windows.

    The function never fits or tunes a model on the test segment. Scores are
    treated as already-generated point-in-time observations; callers that fit
    models must do so using each window's training segment only.
    """

    if len(bars) != len(scores):
        raise ValueError("bars and scores must have the same length")
    if any(bars[i].timestamp >= bars[i + 1].timestamp for i in range(len(bars) - 1)):
        raise ValueError("bars must be strictly chronological")

    validation_config = validation_config or ValidationConfig()
    backtest_config = backtest_config or BacktestConfig()
    results: list[WalkForwardResult] = []

    for window in build_windows(len(bars), validation_config):
        train_bars = bars[window.train_start:window.train_end]
        train_scores = scores[window.train_start:window.train_end]
        test_bars = bars[window.test_start:window.test_end]
        test_scores = scores[window.test_start:window.test_end]

        train_result = run_backtest(train_bars, train_scores, backtest_config)
        test_result = run_backtest(test_bars, test_scores, backtest_config)
        results.append(
            WalkForwardResult(
                window=window,
                train_metrics=_metrics(train_result, validation_config.min_trades),
                test_metrics=_metrics(test_result, validation_config.min_trades),
            )
        )

    return results
