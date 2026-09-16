from app.core.config import Settings
from app.data.providers.twelve_data import ProviderError, TwelveDataProvider
from app.data.validation import validate_bars, validate_snapshot
from app.models.market import AssetClass, DataStatus, MarketSnapshot, OHLCVBar


class MarketService:
    def __init__(self, settings: Settings):
        self.provider = TwelveDataProvider(settings)
        self.settings = settings

    async def quote(self, symbol: str, asset_class: AssetClass) -> MarketSnapshot:
        try:
            snapshot = await self.provider.quote(symbol.upper(), asset_class)
            return validate_snapshot(snapshot, self.settings)
        except (ProviderError, ValueError, KeyError, TypeError) as exc:
            return MarketSnapshot(
                symbol=symbol.upper(), asset_class=asset_class, price=0.000001,
                timestamp=__import__('datetime').datetime.now(__import__('datetime').timezone.utc),
                source=self.provider.name, status=DataStatus.UNAVAILABLE,
            ).model_copy(update={"price": 0.0})

    async def bars(self, symbol: str, interval: str, outputsize: int = 200) -> list[OHLCVBar]:
        bars = await self.provider.ohlcv(symbol.upper(), interval, outputsize)
        return validate_bars(bars)
