from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache

from app.core.cache import AsyncTTLCache
from app.core.config import Settings, get_settings
from app.data.providers.router import MarketDataRouter
from app.data.providers.twelve_data import ProviderError
from app.data.validation import validate_bars, validate_snapshot
from app.models.market import AssetClass, DataStatus, MarketSnapshot, OHLCVBar


class MarketService:
    """Validated market-data access with process-local TTL caching."""

    def __init__(self, settings: Settings):
        self.provider = MarketDataRouter(settings)
        self.settings = settings
        self._quote_cache: AsyncTTLCache[MarketSnapshot] = AsyncTTLCache(
            default_ttl_seconds=settings.quote_cache_seconds
        )
        self._bars_cache: AsyncTTLCache[list[OHLCVBar]] = AsyncTTLCache(
            default_ttl_seconds=settings.bars_cache_seconds
        )

    async def quote(self, symbol: str, asset_class: AssetClass) -> MarketSnapshot:
        normalized_symbol = symbol.strip().upper()
        key = f"quote:{asset_class.value}:{normalized_symbol}"

        async def fetch() -> MarketSnapshot:
            try:
                snapshot = await self.provider.quote(normalized_symbol, asset_class)
                return validate_snapshot(snapshot, self.settings)
            except (ProviderError, ValueError, KeyError, TypeError):
                return MarketSnapshot(
                    symbol=normalized_symbol,
                    asset_class=asset_class,
                    price=None,
                    timestamp=datetime.now(timezone.utc),
                    source="market-provider-router",
                    status=DataStatus.UNAVAILABLE,
                )

        snapshot = await self._quote_cache.get_or_set(
            key, fetch, ttl_seconds=self.settings.quote_cache_seconds
        )
        return validate_snapshot(snapshot, self.settings)

    async def bars(
        self,
        symbol: str,
        interval: str,
        outputsize: int = 200,
    ) -> list[OHLCVBar]:
        normalized_symbol = symbol.strip().upper()
        normalized_interval = interval.strip().lower()
        key = f"bars:{normalized_symbol}:{normalized_interval}:{outputsize}"

        async def fetch() -> list[OHLCVBar]:
            bars = await self.provider.ohlcv(
                normalized_symbol, normalized_interval, outputsize
            )
            return validate_bars(bars)

        return await self._bars_cache.get_or_set(
            key, fetch, ttl_seconds=self.settings.bars_cache_seconds
        )


@lru_cache(maxsize=1)
def get_market_service() -> MarketService:
    """Return the process-wide market service so caches survive HTTP requests."""

    return MarketService(get_settings())
