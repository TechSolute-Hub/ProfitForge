from __future__ import annotations

from datetime import datetime, timezone

from app.backtest.outcomes import label_outcome
from app.core.config import Settings
from app.learning.persistence import ModelPersistenceError, SupabaseModelRepository
from app.services.market import MarketService
from app.data.providers.twelve_data import ProviderError


class OutcomeVerificationService:
    """Verify stored signal outcomes against historical market data."""

    def __init__(
        self,
        settings: Settings,
        market_service: MarketService,
        repository: SupabaseModelRepository | None = None,
    ) -> None:
        self.settings = settings
        self.market_service = market_service
        self.repository = repository or SupabaseModelRepository(settings)

    async def verify_pending(self, limit: int = 100) -> int:
        rows = await self.repository.pending_signal_outcomes(limit)
        verified = 0
        for row in rows:
            try:
                if await self._verify_one(row):
                    verified += 1
            except (ValueError, KeyError, ModelPersistenceError, ProviderError):
                continue
        return verified

    async def _verify_one(self, row: dict[str, object]) -> bool:
        signal_time = datetime.fromisoformat(
            str(row["signal_time"]).replace("Z", "+00:00")
        )
        if signal_time.tzinfo is None:
            signal_time = signal_time.replace(tzinfo=timezone.utc)

        timeframe = str(row["timeframe"])
        horizon_bars = int(row["horizon_bars"])
        bars = await self.market_service.bars(
            str(row["symbol"]),
            timeframe,
            max(250, horizon_bars + 10),
        )
        signal_index = next(
            (
                index
                for index, bar in enumerate(bars)
                if bar.timestamp == signal_time
            ),
            None,
        )
        if signal_index is None:
            return False

        outcome = label_outcome(bars, signal_index, horizon_bars)
        if outcome.forward_return_pct is None:
            return False

        await self.repository.mark_signal_outcome_verified(
            str(row["id"]),
            outcome.forward_return_pct,
            outcome.label,
            outcome.signal_time,
        )
        return True
