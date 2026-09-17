from __future__ import annotations

from dataclasses import dataclass

from app.models.market import OHLCVBar


@dataclass(frozen=True)
class StructureSnapshot:
    bias: str
    swing_high: float | None
    swing_low: float | None
    previous_swing_high: float | None
    previous_swing_low: float | None
    high_sequence: str
    low_sequence: str
    bos: str | None
    choch: str | None
    support: float | None
    resistance: float | None


def _pivots(bars: list[OHLCVBar], lookback: int = 2) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    if len(bars) < 2 * lookback + 5:
        raise ValueError("not enough bars for structure analysis")
    # A pivot is only usable after its right-side confirmation bars have closed.
    highs: list[tuple[int, float]] = []
    lows: list[tuple[int, float]] = []
    end = len(bars) - lookback
    for index in range(lookback, end):
        window = bars[index - lookback : index + lookback + 1]
        high = bars[index].high
        low = bars[index].low
        if high == max(bar.high for bar in window) and sum(bar.high == high for bar in window) == 1:
            highs.append((index, high))
        if low == min(bar.low for bar in window) and sum(bar.low == low for bar in window) == 1:
            lows.append((index, low))
    return highs, lows


def analyze_structure(bars: list[OHLCVBar], lookback: int = 2) -> StructureSnapshot:
    highs, lows = _pivots(bars, lookback)
    if len(highs) < 2 or len(lows) < 2:
        return StructureSnapshot("NEUTRAL", None, None, None, None, "UNKNOWN", "UNKNOWN", None, None, None, None)
    previous_high = highs[-2][1]
    current_high = highs[-1][1]
    previous_low = lows[-2][1]
    current_low = lows[-1][1]
    high_sequence = "HH" if current_high > previous_high else "LH" if current_high < previous_high else "EQH"
    low_sequence = "HL" if current_low > previous_low else "LL" if current_low < previous_low else "EQL"
    if high_sequence == "HH" and low_sequence == "HL":
        bias = "BULLISH"
    elif high_sequence == "LH" and low_sequence == "LL":
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    close = bars[-1].close
    bos = None
    if close > current_high:
        bos = "BULLISH"
    elif close < current_low:
        bos = "BEARISH"

    prior_bias = "BULLISH" if highs[-2][1] > (highs[-3][1] if len(highs) >= 3 else highs[-2][1]) and current_low > previous_low else None
    if prior_bias == "BULLISH" and close < current_low:
        choch = "BEARISH"
    elif bias == "BEARISH" and close > current_high:
        choch = "BULLISH"
    else:
        choch = None

    return StructureSnapshot(
        bias=bias,
        swing_high=current_high,
        swing_low=current_low,
        previous_swing_high=previous_high,
        previous_swing_low=previous_low,
        high_sequence=high_sequence,
        low_sequence=low_sequence,
        bos=bos,
        choch=choch,
        support=current_low,
        resistance=current_high,
    )
