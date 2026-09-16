from datetime import datetime, timezone
import time
import httpx
from app.core.config import Settings
from app.data.providers.base import MarketDataProvider
from app.models.market import AssetClass, DataStatus, MarketSnapshot, OHLCVBar


class ProviderError(RuntimeError):
    pass


class TwelveDataProvider(MarketDataProvider):
    name = "Twelve Data"

    def __init__(self, settings: Settings):
        self.settings = settings

    def _require_key(self) -> None:
        if not self.settings.twelve_data_api_key:
            raise ProviderError("Twelve Data API key is not configured")

    async def _get(self, endpoint: str, params: dict) -> dict:
        self._require_key()
        started = time.perf_counter()
        params = {**params, "apikey": self.settings.twelve_data_api_key}
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(f"{self.settings.twelve_data_base_url}/{endpoint}", params=params)
        elapsed = (time.perf_counter() - started) * 1000
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("status") == "error":
            raise ProviderError(str(payload.get("message", "Provider error")))
        payload["_latency_ms"] = elapsed
        return payload

    async def quote(self, symbol: str, asset_class: AssetClass) -> MarketSnapshot:
        payload = await self._get("price", {"symbol": symbol})
        price = float(payload["price"])
        timestamp = datetime.now(timezone.utc)
        return MarketSnapshot(
            symbol=symbol.upper(), asset_class=asset_class, price=price,
            timestamp=timestamp, source=self.name, status=DataStatus.LIVE,
            latency_ms=payload.get("_latency_ms"),
        )

    async def ohlcv(self, symbol: str, interval: str, outputsize: int = 200) -> list[OHLCVBar]:
        payload = await self._get("time_series", {
            "symbol": symbol, "interval": interval, "outputsize": outputsize,
            "order": "ASC",
        })
        values = payload.get("values", [])
        bars: list[OHLCVBar] = []
        for row in reversed(values):
            bars.append(OHLCVBar(
                timestamp=datetime.fromisoformat(row["datetime"].replace("Z", "+00:00")),
                open=float(row["open"]), high=float(row["high"]),
                low=float(row["low"]), close=float(row["close"]),
                volume=float(row["volume"]) if row.get("volume") not in (None, "") else None,
            ))
        return sorted(bars, key=lambda x: x.timestamp)
