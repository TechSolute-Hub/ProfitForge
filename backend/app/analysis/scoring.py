from __future__ import annotations

from dataclasses import dataclass

from app.analysis.indicators import IndicatorSnapshot
from app.analysis.structure import StructureSnapshot


@dataclass(frozen=True)
class FactorAssessment:
    score: float
    weight: float
    available: bool
    reason: str


WEIGHTS = {
    "htf_trend": 0.25,
    "momentum": 0.25,
    "volume_confirmation": 0.15,
    "market_structure": 0.20,
    "news_sentiment": 0.15,
}


def _clamp(value: float) -> float:
    return max(-100.0, min(100.0, value))


def assess_factors(
    bars: list,
    indicators: IndicatorSnapshot,
    structure: StructureSnapshot,
) -> dict[str, FactorAssessment]:
    trend = 0.0
    if indicators.ema20 > indicators.ema50 > indicators.ema200:
        trend = 100.0
    elif indicators.ema20 < indicators.ema50 < indicators.ema200:
        trend = -100.0
    elif indicators.ema20 > indicators.ema50:
        trend = 45.0
    elif indicators.ema20 < indicators.ema50:
        trend = -45.0

    momentum = 0.0
    if indicators.rsi14 >= 60:
        momentum += 45.0
    elif indicators.rsi14 >= 52:
        momentum += 20.0
    elif indicators.rsi14 <= 40:
        momentum -= 45.0
    elif indicators.rsi14 <= 48:
        momentum -= 20.0
    if indicators.macd_histogram > 0:
        momentum += 35.0
    elif indicators.macd_histogram < 0:
        momentum -= 35.0
    if indicators.adx14 >= 25:
        momentum *= 1.15
    momentum = _clamp(momentum)

    volume_values = [bar.volume for bar in bars if bar.volume is not None]
    if len(volume_values) >= 20:
        baseline = sum(volume_values[-21:-1]) / 20.0
        ratio = volume_values[-1] / baseline if baseline else 1.0
        price_direction = 1.0 if bars[-1].close >= bars[-2].close else -1.0
        volume_score = _clamp((ratio - 1.0) * 100.0 * price_direction)
        volume_reason = f"Latest volume is {ratio:.2f}x its 20-bar baseline."
        volume_available = True
    else:
        volume_score = 0.0
        volume_reason = "Volume is unavailable or insufficient for confirmation."
        volume_available = False

    structure_score = 0.0
    if structure.bias == "BULLISH":
        structure_score = 80.0
    elif structure.bias == "BEARISH":
        structure_score = -80.0
    if structure.bos == "BULLISH":
        structure_score = 100.0
    elif structure.bos == "BEARISH":
        structure_score = -100.0

    return {
        "htf_trend": FactorAssessment(trend, WEIGHTS["htf_trend"], True, "EMA20/50/200 alignment."),
        "momentum": FactorAssessment(momentum, WEIGHTS["momentum"], True, "RSI, MACD histogram and ADX."),
        "volume_confirmation": FactorAssessment(volume_score, WEIGHTS["volume_confirmation"], volume_available, volume_reason),
        "market_structure": FactorAssessment(structure_score, WEIGHTS["market_structure"], True, f"{structure.high_sequence}/{structure.low_sequence} structure."),
        "news_sentiment": FactorAssessment(0.0, WEIGHTS["news_sentiment"], False, "News/sentiment provider is not enabled in Phase 2; no value is fabricated."),
    }


def aggregate_score(factors: dict[str, FactorAssessment]) -> tuple[int, dict[str, float], float]:
    available_weight = sum(item.weight for item in factors.values() if item.available)
    if available_weight <= 0:
        return 0, {name: 0.0 for name in factors}, 0.0
    weighted = sum(item.score * item.weight for item in factors.values() if item.available)
    score = round(_clamp(weighted / available_weight))
    contributions = {
        name: round(item.score * item.weight / available_weight, 2) if item.available else 0.0
        for name, item in factors.items()
    }
    return score, contributions, available_weight


def confidence_score(score: int, factors: dict[str, FactorAssessment], mtf_alignment: float = 0.0) -> int:
    available = [item.score for item in factors.values() if item.available]
    if not available:
        return 0
    direction = 1 if score > 0 else -1 if score < 0 else 0
    agreement = sum(1 for value in available if direction and value * direction >= 20) / len(available) if direction else 0.0
    confidence = 45.0 + abs(score) * 0.30 + agreement * 15.0 + mtf_alignment * 15.0
    return max(25, min(95, round(confidence)))
