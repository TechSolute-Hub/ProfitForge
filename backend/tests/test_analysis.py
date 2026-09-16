from datetime import datetime, timedelta, timezone
from app.models.market import OHLCVBar
from app.services.analysis import analyze_bars


def test_analysis_is_deterministic():
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    bars = [OHLCVBar(timestamp=start + timedelta(days=i), open=100+i, high=102+i, low=99+i, close=101+i, volume=1000) for i in range(80)]
    first = analyze_bars(bars)
    second = analyze_bars(bars)
    assert first == second
    assert -100 <= first['score'] <= 100
    assert 0 <= first['confidence'] <= 100
