from datetime import datetime, timezone

import pytest

from app.core.config import Settings
from app.data.providers.alpha_vantage import AlphaVantageProvider
from app.data.providers.base import MarketDataProvider
from app.data.providers.router import MarketDataRouter
from app.data.providers.twelve_data import ProviderError
from app.models.market import AssetClass, DataStatus, MarketSnapshot, OHLCVBar


class FailingProvider(MarketDataProvider):
    name = "failing"

    async def quote(self, symbol: str, asset_class: AssetClass) -> MarketSnapshot:
        raise ProviderError("primary failed")

    async def ohlcv(self, symbol: str, interval: str, outputsize: int = 200) -> list[OHLCVBar]:
        raise ProviderError("primary failed")


class WorkingProvider(MarketDataProvider):
    name = "working"

    async def quote(self, symbol: str, asset_class: AssetClass) -> MarketSnapshot:
        return MarketSnapshot(
            symbol=symbol,
            asset_class=asset_class,
            price=123.45,
            timestamp=datetime.now(timezone.utc),
            source=self.name,
            status=DataStatus.LIVE,
        )

    async def ohlcv(self, symbol: str, interval: str, outputsize: int = 200) -> list[OHLCVBar]:
        now = datetime.now(timezone.utc)
        return [
            OHLCVBar(
                timestamp=now,
                open=1,
                high=2,
                low=1,
                close=1.5,
                volume=10,
            )
        ]


@pytest.mark.asyncio
async def test_router_uses_next_provider_after_failure() -> None:
    settings = Settings()
    router = MarketDataRouter(settings)
    router.providers = [FailingProvider(), WorkingProvider()]

    snapshot = await router.quote("AAPL", AssetClass.STOCK)
    bars = await router.ohlcv("AAPL", "1day", 10)

    assert snapshot.source == "working"
    assert snapshot.price == 123.45
    assert len(bars) == 1


@pytest.mark.asyncio
async def test_alpha_vantage_daily_parser_returns_sorted_bars() -> None:
    settings = Settings(alpha_vantage_api_key="test")
    provider = AlphaVantageProvider(settings)

    async def fake_get(_: dict[str, str]) -> dict[str, object]:
        return {
            "Time Series (Daily)": {
                "2026-09-16": {
                    "1. open": "101",
                    "2. high": "105",
                    "3. low": "99",
                    "4. close": "104",
                    "5. volume": "1000",
                },
                "2026-09-15": {
                    "1. open": "98",
                    "2. high": "102",
                    "3. low": "97",
                    "4. close": "101",
                    "5. volume": "900",
                },
            }
        }

    provider._get = fake_get  # type: ignore[method-assign]
    bars = await provider.ohlcv("AAPL", "1day", 2)

    assert [bar.close for bar in bars] == [101.0, 104.0]
    assert bars[0].timestamp < bars[1].timestamp


@pytest.mark.asyncio
async def test_alpha_vantage_stock_quote_is_marked_stale() -> None:
    settings = Settings(alpha_vantage_api_key="test")
    provider = AlphaVantageProvider(settings)

    async def fake_get(_: dict[str, str]) -> dict[str, object]:
        return {"Global Quote": {"05. price": "100.25"}}

    provider._get = fake_get  # type: ignore[method-assign]
    snapshot = await provider.quote("AAPL", AssetClass.STOCK)

    assert snapshot.price == 100.25
    assert snapshot.status == DataStatus.STALE
