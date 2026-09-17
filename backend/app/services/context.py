from __future__ import annotations

import asyncio
from functools import lru_cache

from app.core.cache import AsyncTTLCache
from app.core.config import Settings, get_settings
from app.data.providers.alpha_vantage_context import AlphaVantageContextProvider
from app.models.context import EconomicContext, MarketContext, NewsSentimentSnapshot
from app.models.market import AssetClass


class MarketContextService:
    """Best-effort contextual data service; unavailable context is never fabricated."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = AlphaVantageContextProvider(settings)
        self._news_cache: AsyncTTLCache[NewsSentimentSnapshot] = AsyncTTLCache(
            default_ttl_seconds=settings.news_cache_seconds
        )
        self._economic_cache: AsyncTTLCache[EconomicContext] = AsyncTTLCache(
            default_ttl_seconds=settings.economic_cache_seconds
        )

    async def news(self, symbol: str, asset_class: AssetClass) -> NewsSentimentSnapshot | None:
        if not self.settings.alpha_vantage_api_key:
            return None
        key = f"news:{asset_class.value}:{symbol.strip().upper()}"
        try:
            return await self._news_cache.get_or_set(
                key,
                lambda: self.provider.news(symbol, asset_class),
                ttl_seconds=self.settings.news_cache_seconds,
            )
        except Exception:
            return None

    async def economic(self, symbol: str, asset_class: AssetClass) -> EconomicContext | None:
        if asset_class != AssetClass.STOCK or not self.settings.alpha_vantage_api_key:
            return None
        key = f"economic:{asset_class.value}:{symbol.strip().upper()}"
        try:
            return await self._economic_cache.get_or_set(
                key,
                lambda: self.provider.earnings(symbol),
                ttl_seconds=self.settings.economic_cache_seconds,
            )
        except Exception:
            return None

    async def context(self, symbol: str, asset_class: AssetClass) -> MarketContext:
        news, economic = await asyncio.gather(
            self.news(symbol, asset_class),
            self.economic(symbol, asset_class),
        )
        return MarketContext(news=news, economic=economic)


@lru_cache(maxsize=1)
def get_market_context_service() -> MarketContextService:
    return MarketContextService(get_settings())
