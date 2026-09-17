from datetime import datetime, timedelta, timezone

from app.analysis.engine import analyze_multi_timeframe, analyze_timeframe
from app.analysis.indicators import compute_indicators, rsi_wilder
from app.models.market import OHLCVBar
from app.services.analysis import analyze_bars


def make_bars(count: int = 260, slope: float = 0.5) -> list[OHLCVBar]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        OHLCVBar(
            timestamp=start + timedelta(days=i),
            open=100 + slope * i,
            high=102 + slope * i,
            low=99 + slope * i,
            close=101 + slope * i,
            volume=1000 + i,
        )
        for i in range(count)
    ]


def test_analysis_is_deterministic():
    bars = make_bars()
    first = analyze_bars(bars)
    second = analyze_bars(bars)
    assert first == second
    assert -100 <= first["score"] <= 100
    assert 0 <= first["confidence"] <= 100


def test_wilder_rsi_is_bounded():
    value = rsi_wilder([100 + i for i in range(40)])
    assert 0 <= value <= 100
    assert value == 100


def test_phase2_indicators_and_timeframe_analysis():
    bars = make_bars()
    indicators = compute_indicators(bars)
    result = analyze_timeframe("1day", bars)
    assert indicators.ema200 > 0
    assert result.bars_used == 260
    assert result.data_quality in {"HIGH", "MODERATE", "LIMITED"}
    assert "news_sentiment" in result.unavailable_factors


def test_multi_timeframe_confluence_is_deterministic():
    bars = make_bars()
    result = analyze_multi_timeframe({"1h": bars, "4h": bars, "1day": bars, "1week": bars}, "1day")
    assert result["bias"] == "BULLISH"
    assert result["alignment"] == 100
    assert -100 <= result["score"] <= 100
