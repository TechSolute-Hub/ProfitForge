from __future__ import annotations

from statistics import median

from app.analysis.indicators import IndicatorSnapshot
from app.models.market import OHLCVBar


REGIMES = ("STRONG_BULL", "BULL", "SIDEWAYS", "BEAR", "STRONG_BEAR", "HIGH_VOLATILITY")


def detect_regime(bars: list[OHLCVBar], indicators: IndicatorSnapshot) -> str:
    closes = [bar.close for bar in bars]
    recent_ranges: list[float] = []
    for index in range(max(1, len(bars) - 60), len(bars)):
        previous = bars[index - 1].close
        recent_ranges.append(max(bars[index].high - bars[index].low, abs(bars[index].high - previous), abs(bars[index].low - previous)))
    baseline = median(recent_ranges) if recent_ranges else indicators.atr14
    if baseline > 0 and indicators.atr14 >= 1.75 * baseline:
        return "HIGH_VOLATILITY"

    close = closes[-1]
    bullish_alignment = close > indicators.ema20 > indicators.ema50 > indicators.ema200
    bearish_alignment = close < indicators.ema20 < indicators.ema50 < indicators.ema200
    if bullish_alignment and indicators.adx14 >= 25:
        return "STRONG_BULL"
    if bearish_alignment and indicators.adx14 >= 25:
        return "STRONG_BEAR"
    if close > indicators.ema50 and indicators.ema20 >= indicators.ema50:
        return "BULL"
    if close < indicators.ema50 and indicators.ema20 <= indicators.ema50:
        return "BEAR"
    return "SIDEWAYS"
