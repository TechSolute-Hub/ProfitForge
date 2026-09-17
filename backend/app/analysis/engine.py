from __future__ import annotations

from dataclasses import asdict, dataclass

from app.analysis.indicators import compute_indicators
from app.analysis.regime import detect_regime
from app.analysis.scoring import aggregate_score, assess_factors, confidence_score
from app.analysis.structure import analyze_structure
from app.models.market import OHLCVBar


TIMEFRAME_ORDER = ("1week", "1day", "4h", "1h")
MTF_WEIGHTS = {"1week": 0.10, "1day": 0.40, "4h": 0.35, "1h": 0.15}


@dataclass(frozen=True)
class TimeframeAnalysis:
    timeframe: str
    score: int
    bias: str
    confidence: int
    regime: str
    factors: dict[str, float]
    contributions: dict[str, float]
    indicators: dict[str, float]
    structure: dict[str, object]
    bars_used: int
    data_quality: str
    unavailable_factors: list[str]


def _bias(score: int) -> str:
    if score > 20:
        return "BULLISH"
    if score < -20:
        return "BEARISH"
    return "NEUTRAL"


def analyze_timeframe(timeframe: str, bars: list[OHLCVBar], mtf_alignment: float = 0.0) -> TimeframeAnalysis:
    if len(bars) < 220:
        raise ValueError(f"{timeframe}: at least 220 bars are required")
    indicators = compute_indicators(bars)
    structure = analyze_structure(bars)
    regime = detect_regime(bars, indicators)
    assessments = assess_factors(bars, indicators, structure)
    score, contributions, available_weight = aggregate_score(assessments)
    confidence = confidence_score(score, assessments, mtf_alignment)
    factor_scores = {name: round(item.score, 2) for name, item in assessments.items()}
    unavailable = [name for name, item in assessments.items() if not item.available]
    quality = "HIGH" if available_weight >= 0.85 else "MODERATE" if available_weight >= 0.70 else "LIMITED"
    indicator_values = asdict(indicators)
    structure_values = asdict(structure)
    return TimeframeAnalysis(
        timeframe=timeframe, score=score, bias=_bias(score), confidence=confidence, regime=regime,
        factors=factor_scores, contributions=contributions, indicators=indicator_values,
        structure=structure_values, bars_used=len(bars), data_quality=quality,
        unavailable_factors=unavailable,
    )


def analyze_multi_timeframe(bars_by_timeframe: dict[str, list[OHLCVBar]], primary: str = "1day") -> dict[str, object]:
    analyses: dict[str, TimeframeAnalysis] = {}
    for timeframe in TIMEFRAME_ORDER:
        bars = bars_by_timeframe.get(timeframe)
        if bars:
            analyses[timeframe] = analyze_timeframe(timeframe, bars)

    if primary not in analyses:
        raise ValueError(f"primary timeframe {primary!r} is unavailable")

    primary_analysis = analyses[primary]
    primary_direction = 1 if primary_analysis.score > 20 else -1 if primary_analysis.score < -20 else 0
    weighted_scores = []
    total_weight = 0.0
    aligned_weight = 0.0
    for timeframe, analysis in analyses.items():
        weight = MTF_WEIGHTS.get(timeframe, 0.0)
        weighted_scores.append(analysis.score * weight)
        total_weight += weight
        if primary_direction and ((analysis.score > 20 and primary_direction > 0) or (analysis.score < -20 and primary_direction < 0)):
            aligned_weight += weight
    mtf_score = round(sum(weighted_scores) / total_weight) if total_weight else primary_analysis.score
    alignment = aligned_weight / total_weight if total_weight else 0.0
    final_score = round(max(-100, min(100, 0.75 * primary_analysis.score + 0.25 * mtf_score)))
    final_bias = _bias(final_score)
    return {
        "primary": primary,
        "score": final_score,
        "bias": final_bias,
        "mtf_score": mtf_score,
        "alignment": round(alignment * 100),
        "timeframes": {key: asdict(value) for key, value in analyses.items()},
        "confidence": confidence_score(final_score, {
            name: type("Factor", (), {"score": value, "available": True})() for name, value in primary_analysis.factors.items()
        }, alignment),
    }
