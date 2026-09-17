from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.models.market import OHLCVBar


@dataclass(frozen=True)
class BacktestConfig:
    """Execution assumptions for deterministic research validation."""

    initial_equity: float = 10_000.0
    signal_threshold: int = 60
    holding_bars: int = 12
    stop_loss_pct: float = 0.02
    take_profit_pct: float = 0.04
    fee_bps: float = 5.0
    slippage_bps: float = 2.0

    def __post_init__(self) -> None:
        if self.initial_equity <= 0:
            raise ValueError("initial_equity must be positive")
        if not 0 < self.signal_threshold <= 100:
            raise ValueError("signal_threshold must be in 1..100")
        if self.holding_bars < 1:
            raise ValueError("holding_bars must be positive")
        if not 0 < self.stop_loss_pct < 1:
            raise ValueError("stop_loss_pct must be between 0 and 1")
        if not 0 < self.take_profit_pct < 1:
            raise ValueError("take_profit_pct must be between 0 and 1")
        if self.fee_bps < 0 or self.slippage_bps < 0:
            raise ValueError("cost assumptions cannot be negative")


@dataclass(frozen=True)
class BacktestTrade:
    signal_time: datetime
    entry_time: datetime
    exit_time: datetime
    direction: str
    entry_price: float
    exit_price: float
    gross_return_pct: float
    costs_pct: float
    net_return_pct: float
    exit_reason: str


@dataclass(frozen=True)
class BacktestResult:
    initial_equity: float
    final_equity: float
    total_return_pct: float
    trade_count: int
    win_count: int
    loss_count: int
    win_rate_pct: float
    max_drawdown_pct: float
    trades: list[BacktestTrade]


def _signal(score: int, threshold: int) -> str | None:
    if score >= threshold:
        return "LONG"
    if score <= -threshold:
        return "SHORT"
    return None


def _simulate_trade(
    bars: list[OHLCVBar],
    signal_index: int,
    direction: str,
    config: BacktestConfig,
) -> BacktestTrade | None:
    entry_index = signal_index + 1
    if entry_index >= len(bars):
        return None

    entry_bar = bars[entry_index]
    entry_raw = entry_bar.open
    slip = config.slippage_bps / 10_000
    entry_price = entry_raw * (1 + slip if direction == "LONG" else 1 - slip)

    stop = entry_price * (1 - config.stop_loss_pct if direction == "LONG" else 1 + config.stop_loss_pct)
    target = entry_price * (1 + config.take_profit_pct if direction == "LONG" else 1 - config.take_profit_pct)
    last_index = min(len(bars) - 1, entry_index + config.holding_bars)

    exit_index = last_index
    exit_price = bars[last_index].close
    exit_reason = "TIME"

    for index in range(entry_index, last_index + 1):
        bar = bars[index]
        if direction == "LONG":
            # Conservative ordering when both levels are touched in one candle:
            # assume the stop was hit first because intrabar order is unknown.
            if bar.low <= stop:
                exit_index, exit_price, exit_reason = index, stop, "STOP"
                break
            if bar.high >= target:
                exit_index, exit_price, exit_reason = index, target, "TARGET"
                break
        else:
            if bar.high >= stop:
                exit_index, exit_price, exit_reason = index, stop, "STOP"
                break
            if bar.low <= target:
                exit_index, exit_price, exit_reason = index, target, "TARGET"
                break

    exit_slip = config.slippage_bps / 10_000
    execution_exit = exit_price * (1 - exit_slip if direction == "LONG" else 1 + exit_slip)
    gross = (execution_exit / entry_price - 1) if direction == "LONG" else (entry_price / execution_exit - 1)
    costs = 2 * (config.fee_bps / 10_000)

    return BacktestTrade(
        signal_time=bars[signal_index].timestamp,
        entry_time=entry_bar.timestamp,
        exit_time=bars[exit_index].timestamp,
        direction=direction,
        entry_price=entry_price,
        exit_price=execution_exit,
        gross_return_pct=gross * 100,
        costs_pct=costs * 100,
        net_return_pct=(gross - costs) * 100,
        exit_reason=exit_reason,
    )


def run_backtest(
    bars: list[OHLCVBar],
    scores: list[int],
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run a no-look-ahead score backtest.

    `scores[i]` is assumed to be known only after bar `i` closes. Entries therefore
    occur at bar `i + 1` open. No future bar is used to create a signal.
    """

    config = config or BacktestConfig()
    if len(bars) != len(scores):
        raise ValueError("bars and scores must have the same length")
    if len(bars) < 2:
        raise ValueError("at least two bars are required")
    if any(bars[index].timestamp >= bars[index + 1].timestamp for index in range(len(bars) - 1)):
        raise ValueError("bars must be strictly chronological")

    trades: list[BacktestTrade] = []
    next_available_index = 0
    equity = config.initial_equity
    peak = equity
    max_drawdown = 0.0

    for signal_index in range(len(bars) - 1):
        if signal_index < next_available_index:
            continue
        direction = _signal(scores[signal_index], config.signal_threshold)
        if direction is None:
            continue
        trade = _simulate_trade(bars, signal_index, direction, config)
        if trade is None:
            continue
        trades.append(trade)
        equity *= 1 + trade.net_return_pct / 100
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak * 100)
        exit_index = next(i for i, bar in enumerate(bars) if bar.timestamp == trade.exit_time)
        next_available_index = exit_index + 1

    wins = sum(1 for trade in trades if trade.net_return_pct > 0)
    losses = sum(1 for trade in trades if trade.net_return_pct <= 0)
    total_return = (equity / config.initial_equity - 1) * 100
    return BacktestResult(
        initial_equity=config.initial_equity,
        final_equity=equity,
        total_return_pct=total_return,
        trade_count=len(trades),
        win_count=wins,
        loss_count=losses,
        win_rate_pct=(wins / len(trades) * 100) if trades else 0.0,
        max_drawdown_pct=max_drawdown,
        trades=trades,
    )
