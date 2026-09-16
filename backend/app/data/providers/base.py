from abc import ABC, abstractmethod
from datetime import datetime
from app.models.market import AssetClass, MarketSnapshot, OHLCVBar


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    async def quote(self, symbol: str, asset_class: AssetClass) -> MarketSnapshot:
        raise NotImplementedError

    @abstractmethod
    async def ohlcv(self, symbol: str, interval: str, outputsize: int = 200) -> list[OHLCVBar]:
        raise NotImplementedError
