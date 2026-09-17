from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    title: str
    url: str
    source: str
    published_at: datetime
    sentiment_score: float = Field(ge=-1, le=1)
    sentiment_label: str
    relevance: float = Field(ge=0, le=1)


class NewsSentimentSnapshot(BaseModel):
    symbol: str
    asset_class: str
    score: float = Field(ge=-100, le=100)
    label: str
    article_count: int = Field(ge=0)
    source: str
    observed_at: datetime
    items: list[NewsItem] = Field(default_factory=list)


class EconomicEvent(BaseModel):
    symbol: str | None = None
    event_type: str
    event_date: datetime
    description: str
    importance: str = "unknown"
    source: str


class EconomicContext(BaseModel):
    symbol: str
    asset_class: str
    events: list[EconomicEvent] = Field(default_factory=list)
    source: str
    observed_at: datetime
    available: bool = True


class MarketContext(BaseModel):
    news: NewsSentimentSnapshot | None = None
    economic: EconomicContext | None = None
