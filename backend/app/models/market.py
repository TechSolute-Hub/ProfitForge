from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class AssetClass(str, Enum):
    STOCK = "stock"
    FOREX = "forex"
    CRYPTO = "crypto"


class DataStatus(str, Enum):
    LIVE = "LIVE"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"


class MarketSnapshot(BaseModel):
    symbol: str
    asset_class: AssetClass
    price: float = Field(gt=0)
    timestamp: datetime
    source: str
    status: DataStatus
    currency: str | None = None
    latency_ms: float | None = None


class OHLCVBar(BaseModel):
    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float | None = Field(default=None, ge=0)


class ResearchResult(BaseModel):
    symbol: str
    asset_class: AssetClass
    snapshot: MarketSnapshot
    timeframe: str
    bias: str
    score: int = Field(ge=-100, le=100)
    confidence: int = Field(ge=0, le=100)
    regime: str
    factors: dict[str, float]
    explanation: list[str]
    invalidation: str
    alternative_scenario: str
    bars_used: int
    disclaimer: str
