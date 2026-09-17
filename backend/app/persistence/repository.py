from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.models.market import AssetClass


@dataclass(frozen=True, slots=True)
class WatchlistItem:
    user_id: UUID
    symbol: str
    asset_class: AssetClass
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class SavedAnalysis:
    user_id: UUID
    name: str
    symbol: str
    asset_class: AssetClass
    timeframe: str
    result: dict[str, object]
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ResearchHistoryRecord:
    user_id: UUID
    symbol: str
    asset_class: AssetClass
    timeframe: str
    score: int
    confidence: int
    bias: str
    regime: str
    result: dict[str, object]
    observed_at: datetime


class ResearchRepository(Protocol):
    """Persistence contract independent of Supabase or another database."""

    async def add_watchlist_item(self, item: WatchlistItem) -> None:
        """Persist a symbol in the user's watchlist."""

    async def remove_watchlist_item(
        self,
        user_id: UUID,
        symbol: str,
        asset_class: AssetClass,
    ) -> None:
        """Remove a symbol from the user's watchlist."""

    async def save_analysis(self, analysis: SavedAnalysis) -> None:
        """Persist a named research snapshot."""

    async def record_history(self, record: ResearchHistoryRecord) -> None:
        """Persist an immutable research observation."""
