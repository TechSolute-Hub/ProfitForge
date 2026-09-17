from __future__ import annotations

from dataclasses import dataclass

from app.models.market import OHLCVBar


@dataclass(frozen=True)
class OutcomeLabel:
    signal_index: int
    signal_time: object
    entry_price: float
    horizon_bars: int
    forward_return_pct: float | None
    direction: str
    label: str


def label_outcome(
    bars: list[OHLCVBar],
    signal_index: int,
    horizon_bars: int,
    bullish_threshold_pct: float = 1.0,
    bearish_threshold_pct: float = -1.0,
) -> OutcomeLabel:
    """Label a signal using only prices strictly after its signal bar."""

    if not 0 <= signal_index < len(bars):
        raise ValueError("signal_index is outside the bar series")
    if horizon_bars < 1:
        raise ValueError("horizon_bars must be positive")
    if bullish_threshold_pct <= 0 or bearish_threshold_pct >= 0:
        raise ValueError("thresholds must be positive for bullish and negative for bearish")

    future_index = signal_index + horizon_bars
    entry_index = signal_index + 1
    if future_index >= len(bars):
        return OutcomeLabel(
            signal_index=signal_index,
            signal_time=bars[signal_index].timestamp,
            entry_price=bars[entry_index].open if entry_index < len(bars) else bars[signal_index].close,
            horizon_bars=horizon_bars,
            forward_return_pct=None,
            direction="UNRESOLVED",
            label="INSUFFICIENT_FUTURE_DATA",
        )

    entry_price = bars[entry_index].open
    exit_price = bars[future_index].close
    forward_return = (exit_price / entry_price - 1) * 100
    if forward_return >= bullish_threshold_pct:
        direction, label = "BULLISH", "POSITIVE"
    elif forward_return <= bearish_threshold_pct:
        direction, label = "BEARISH", "NEGATIVE"
    else:
        direction, label = "NEUTRAL", "NEUTRAL"

    return OutcomeLabel(
        signal_index=signal_index,
        signal_time=bars[signal_index].timestamp,
        entry_price=entry_price,
        horizon_bars=horizon_bars,
        forward_return_pct=forward_return,
        direction=direction,
        label=label,
    )
