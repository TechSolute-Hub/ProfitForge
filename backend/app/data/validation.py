from datetime import datetime, timezone
from app.core.config import Settings
from app.models.market import DataStatus, MarketSnapshot, OHLCVBar


def validate_bars(bars: list[OHLCVBar]) -> list[OHLCVBar]:
    if len(bars) < 30:
        raise ValueError("Insufficient OHLCV history; at least 30 bars are required")
    for previous, current in zip(bars, bars[1:]):
        if current.timestamp <= previous.timestamp:
            raise ValueError("OHLCV timestamps must be strictly increasing")
        if current.high < max(current.open, current.close) or current.low > min(current.open, current.close):
            raise ValueError("Invalid OHLCV range")
        if current.high < current.low:
            raise ValueError("High cannot be below low")
    return bars


def validate_snapshot(snapshot: MarketSnapshot, settings: Settings) -> MarketSnapshot:
    age = (datetime.now(timezone.utc) - snapshot.timestamp.astimezone(timezone.utc)).total_seconds()
    if age > settings.max_data_age_seconds:
        snapshot.status = DataStatus.STALE
    if age < -60:
        snapshot.status = DataStatus.INVALID
    return snapshot
