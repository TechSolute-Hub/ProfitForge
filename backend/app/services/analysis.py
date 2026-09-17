from __future__ import annotations

from app.analysis.engine import analyze_timeframe
from app.models.market import OHLCVBar


def sma(values: list[float], period: int) -> float:
    if period <= 0 or len(values) < period:
        raise ValueError("insufficient values for SMA")
    return sum(values[-period:]) / period


def ema(values: list[float], period: int) -> float:
    if period <= 0 or len(values) < period:
        raise ValueError("insufficient values for EMA")
    alpha = 2 / (period + 1)
    value = values[0]
    for item in values[1:]:
        value = alpha * item + (1 - alpha) * value
    return value


def rsi(closes: list[float], period: int = 14) -> float:
    from app.analysis.indicators import rsi_wilder

    return rsi_wilder(closes, period)


def atr(bars: list[OHLCVBar], period: int = 14) -> float:
    from app.analysis.indicators import atr as calculate_atr

    return calculate_atr(bars, period)


def analyze_bars(bars: list[OHLCVBar]) -> dict:
    """Backward-compatible single-timeframe Phase 2 analysis entry point."""
    result = analyze_timeframe("1day", bars)
    return {
        "score": result.score,
        "confidence": result.confidence,
        "bias": result.bias,
        "regime": result.regime,
        "factors": result.factors,
        "contributions": result.contributions,
        "rsi": result.indicators["rsi14"],
        "ema20": result.indicators["ema20"],
        "ema50": result.indicators["ema50"],
        "ema200": result.indicators["ema200"],
        "atr": result.indicators["atr14"],
        "structure": result.structure,
    }
