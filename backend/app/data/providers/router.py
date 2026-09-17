from __future__ import annotations

from collections.abc import Iterable

from app.core.config import Settings
from app.data.providers.alpha_vantage import AlphaVantageProvider
from app.data.providers.base import MarketDataProvider
from app.data.providers.twelve_data import ProviderError, TwelveDataProvider
from app.models.market import AssetClass, MarketSnapshot, OHLCVBar


class MarketDataRouter:
    """Try configured providers in deterministic priority order."""

    def __init__(self, settings: Settings):
        providers: list[MarketDataProvider] = [TwelveDataProvider(settings)]
        if settings.alpha_vantage_api_key:
            providers.append(AlphaVantageProvider(settings))
        self.providers = providers

    @staticmethod
    def _ordered(providers: Iterable[MarketDataProvider]) -> list[MarketDataProvider]:
        return list(providers)

    async def quote(self, symbol: str, asset_class: AssetClass) -> MarketSnapshot:
        errors: list[str] = []
        for provider in self._ordered(self.providers):
            try:
                snapshot = await provider.quote(symbol, asset_class)
                if snapshot.status.value == "STALE":
                    errors.append(f"{provider.name}: stale quote")
                    continue
                return snapshot
            except (ProviderError, ValueError, KeyError, TypeError) as exc:
                errors.append(f"{provider.name}: {exc}")
        raise ProviderError("No configured provider returned a usable current quote")

    async def ohlcv(
        self,
        symbol: str,
        interval: str,
        outputsize: int = 200,
    ) -> list[OHLCVBar]:
        errors: list[str] = []
        for provider in self._ordered(self.providers):
            try:
                bars = await provider.ohlcv(symbol, interval, outputsize)
                if bars:
                    return bars
            except (ProviderError, ValueError, KeyError, TypeError) as exc:
                errors.append(f"{provider.name}: {exc}")
        raise ProviderError("No configured provider returned usable OHLCV data")
