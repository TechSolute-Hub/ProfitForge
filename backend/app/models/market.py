from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.context import EconomicContext, NewsSentimentSnapshot


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
    price: float | None = Field(default=None, gt=0)
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
    factor_contributions: dict[str, float] = Field(default_factory=dict)
    indicators: dict[str, float] = Field(default_factory=dict)
    structure: dict[str, object] = Field(default_factory=dict)
    mtf_score: int = Field(default=0, ge=-100, le=100)
    mtf_alignment: int = Field(default=0, ge=0, le=100)
    timeframe_analysis: dict[str, object] = Field(default_factory=dict)
    data_quality: str = "UNKNOWN"
    unavailable_factors: list[str] = Field(default_factory=list)
    news_sentiment: NewsSentimentSnapshot | None = None
    economic_context: EconomicContext | None = None
    explanation: list[str]
    invalidation: str
    alternative_scenario: str
    bars_used: int
    disclaimer: str
