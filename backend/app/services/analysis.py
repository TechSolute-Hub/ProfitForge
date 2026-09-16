from statistics import mean
from app.models.market import OHLCVBar


def sma(values: list[float], period: int) -> float:
    return mean(values[-period:])


def ema(values: list[float], period: int) -> float:
    alpha = 2 / (period + 1)
    value = values[0]
    for item in values[1:]:
        value = alpha * item + (1 - alpha) * value
    return value


def rsi(closes: list[float], period: int = 14) -> float:
    changes = [b - a for a, b in zip(closes, closes[1:])]
    gains = [max(x, 0) for x in changes[-period:]]
    losses = [max(-x, 0) for x in changes[-period:]]
    avg_gain = mean(gains)
    avg_loss = mean(losses)
    if avg_loss == 0:
        return 100.0
    return 100 - (100 / (1 + avg_gain / avg_loss))


def atr(bars: list[OHLCVBar], period: int = 14) -> float:
    trs = []
    for i, bar in enumerate(bars):
        prev_close = bars[i - 1].close if i else bar.close
        trs.append(max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close)))
    return mean(trs[-period:])


def analyze_bars(bars: list[OHLCVBar]) -> dict:
    closes = [b.close for b in bars]
    last = closes[-1]
    fast = ema(closes, 20)
    slow = ema(closes, 50)
    rsi_value = rsi(closes)
    atr_value = atr(bars)
    trend = 1 if fast > slow else -1
    momentum = 1 if rsi_value >= 55 else -1 if rsi_value <= 45 else 0
    recent_high = max(b.high for b in bars[-20:])
    recent_low = min(b.low for b in bars[-20:])
    structure = 1 if last > recent_high * 0.995 else -1 if last < recent_low * 1.005 else 0
    volatility_ratio = atr_value / last
    if volatility_ratio > 0.03:
        regime = "High Volatility"
    elif trend > 0 and momentum >= 0:
        regime = "Bull"
    elif trend < 0 and momentum <= 0:
        regime = "Bear"
    else:
        regime = "Sideways"
    factors = {
        "htf_trend": trend,
        "momentum": momentum,
        "market_structure": structure,
        "volatility": min(volatility_ratio * 100, 10),
    }
    raw = 25 * trend + 25 * momentum + 20 * structure
    score = max(-100, min(100, round(raw)))
    confidence = min(95, max(25, round(50 + abs(score) * 0.45)))
    bias = "BULLISH" if score > 20 else "BEARISH" if score < -20 else "NEUTRAL"
    return {
        "score": score, "confidence": confidence, "bias": bias, "regime": regime,
        "factors": factors, "rsi": rsi_value, "ema20": fast, "ema50": slow, "atr": atr_value,
    }
