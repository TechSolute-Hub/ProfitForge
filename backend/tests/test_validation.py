from datetime import datetime, timedelta, timezone
import pytest
from app.data.validation import validate_bars
from app.models.market import OHLCVBar


def bars(n=30):
    start = datetime.now(timezone.utc) - timedelta(days=n)
    return [OHLCVBar(timestamp=start + timedelta(days=i), open=100+i, high=102+i, low=99+i, close=101+i, volume=1000) for i in range(n)]


def test_valid_bars():
    assert len(validate_bars(bars())) == 30


def test_rejects_insufficient_history():
    with pytest.raises(ValueError):
        validate_bars(bars(29))


def test_rejects_non_monotonic_time():
    data = bars()
    data[10], data[11] = data[11], data[10]
    with pytest.raises(ValueError):
        validate_bars(data)
