from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from app.models.market import OHLCVBar


@dataclass(frozen=True)
class IndicatorSnapshot:
    ema20: float
    ema50: float
    ema200: float
    rsi14: float
    macd: float
    macd_signal: float
    macd_histogram: float
    atr14: float
    atr_percent: float
    adx14: float
    stochastic_k: float
    stochastic_d: float


def _require(values: list[float], period: int) -> None:
    if period <= 0:
        raise ValueError("period must be positive")
    if len(values) < period:
        raise ValueError(f"at least {period} values are required")


def ema_series(values: list[float], period: int) -> list[float]:
    _require(values, period)
    alpha = 2.0 / (period + 1.0)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1.0 - alpha) * result[-1])
    return result


def ema(values: list[float], period: int) -> float:
    return ema_series(values, period)[-1]


def rsi_wilder(closes: list[float], period: int = 14) -> float:
    _require(closes, period + 1)
    changes = [b - a for a, b in zip(closes, closes[1:])]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = ((period - 1) * avg_gain + gain) / period
        avg_loss = ((period - 1) * avg_loss + loss) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))


def true_ranges(bars: list[OHLCVBar]) -> list[float]:
    if not bars:
        raise ValueError("bars cannot be empty")
    result: list[float] = []
    for index, bar in enumerate(bars):
        previous = bars[index - 1].close if index else bar.close
        result.append(max(bar.high - bar.low, abs(bar.high - previous), abs(bar.low - previous)))
    return result


def atr(bars: list[OHLCVBar], period: int = 14) -> float:
    ranges = true_ranges(bars)
    _require(ranges, period)
    value = sum(ranges[:period]) / period
    for current in ranges[period:]:
        value = ((period - 1) * value + current) / period
    return value


def _adx_components(bars: list[OHLCVBar], period: int = 14) -> tuple[float, float, float]:
    if len(bars) < period + 1:
        raise ValueError(f"at least {period + 1} bars are required")
    trs: list[float] = []
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    for previous, current in zip(bars, bars[1:]):
        up = current.high - previous.high
        down = previous.low - current.low
        plus_dm.append(up if up > down and up > 0 else 0.0)
        minus_dm.append(down if down > up and down > 0 else 0.0)
        trs.append(max(current.high - current.low, abs(current.high - previous.close), abs(current.low - previous.close)))
    sm_tr = sum(trs[:period])
    sm_plus = sum(plus_dm[:period])
    sm_minus = sum(minus_dm[:period])
    dx_values: list[float] = []
    for index in range(period - 1, len(trs)):
        if index >= period:
            sm_tr = sm_tr - sm_tr / period + trs[index]
            sm_plus = sm_plus - sm_plus / period + plus_dm[index]
            sm_minus = sm_minus - sm_minus / period + minus_dm[index]
        plus_di = 100.0 * sm_plus / sm_tr if sm_tr else 0.0
        minus_di = 100.0 * sm_minus / sm_tr if sm_tr else 0.0
        denominator = plus_di + minus_di
        dx_values.append(100.0 * abs(plus_di - minus_di) / denominator if denominator else 0.0)
    if not dx_values:
        return 0.0, 0.0, 0.0
    adx = sum(dx_values[:period]) / min(period, len(dx_values))
    for value in dx_values[period:]:
        adx = ((period - 1) * adx + value) / period
    return adx, plus_di, minus_di


def _stochastic(bars: list[OHLCVBar], period: int = 14, smooth: int = 3) -> tuple[float, float]:
    _require([bar.close for bar in bars], period)
    values: list[float] = []
    for index in range(period - 1, len(bars)):
        window = bars[index - period + 1 : index + 1]
        high = max(bar.high for bar in window)
        low = min(bar.low for bar in window)
        values.append(100.0 * (bars[index].close - low) / (high - low) if high != low else 50.0)
    k = values[-1]
    d = sum(values[-smooth:]) / min(smooth, len(values))
    return k, d


def compute_indicators(bars: list[OHLCVBar]) -> IndicatorSnapshot:
    if len(bars) < 220:
        raise ValueError("at least 220 bars are required for Phase 2 indicators")
    closes = [bar.close for bar in bars]
    ema20_series = ema_series(closes, 20)
    ema50_series = ema_series(closes, 50)
    ema200_series = ema_series(closes, 200)
    macd_series = [a - b for a, b in zip(ema20_series, ema50_series)]
    signal_series = ema_series(macd_series, 9)
    atr_value = atr(bars, 14)
    adx_value, plus_di, minus_di = _adx_components(bars, 14)
    stochastic_k, stochastic_d = _stochastic(bars)
    del plus_di, minus_di
    return IndicatorSnapshot(
        ema20=ema20_series[-1], ema50=ema50_series[-1], ema200=ema200_series[-1],
        rsi14=rsi_wilder(closes, 14), macd=macd_series[-1],
        macd_signal=signal_series[-1], macd_histogram=macd_series[-1] - signal_series[-1],
        atr14=atr_value, atr_percent=100.0 * atr_value / closes[-1], adx14=adx_value,
        stochastic_k=stochastic_k, stochastic_d=stochastic_d,
    )
