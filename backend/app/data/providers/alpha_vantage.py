from __future__ import annotations

from datetime import datetime, timezone
import time

import httpx

from app.core.config import Settings
from app.data.providers.base import MarketDataProvider
from app.data.providers.twelve_data import ProviderError
from app.models.market import AssetClass, DataStatus, MarketSnapshot, OHLCVBar


class AlphaVantageProvider(MarketDataProvider):
    """Optional historical-data fallback backed by Alpha Vantage."""

    name = "Alpha Vantage"

    def __init__(self, settings: Settings):
        self.settings = settings

    def _require_key(self) -> None:
        if not self.settings.alpha_vantage_api_key:
            raise ProviderError("Alpha Vantage API key is not configured")

    async def _get(self, params: dict[str, str]) -> dict[str, object]:
        self._require_key()
        started = time.perf_counter()
        request_params = {**params, "apikey": self.settings.alpha_vantage_api_key}
        try:
            async with httpx.AsyncClient(timeout=self.settings.provider_request_timeout_seconds) as client:
                response = await client.get(
                    self.settings.alpha_vantage_base_url,
                    params=request_params,
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("Alpha Vantage request failed") from exc

        if not isinstance(payload, dict):
            raise ProviderError("Alpha Vantage returned an invalid response")
        if "Error Message" in payload or "Note" in payload:
            raise ProviderError(str(payload.get("Error Message") or payload.get("Note")))
        payload["_latency_ms"] = (time.perf_counter() - started) * 1000
        return payload

    @staticmethod
    def _fx_symbols(symbol: str) -> tuple[str, str]:
        normalized = symbol.replace("/", "").replace("_", "").upper()
        if len(normalized) != 6:
            raise ProviderError("Alpha Vantage forex symbols must contain six currency letters")
        return normalized[:3], normalized[3:]

    async def quote(self, symbol: str, asset_class: AssetClass) -> MarketSnapshot:
        if asset_class == AssetClass.FOREX:
            from_symbol, to_symbol = self._fx_symbols(symbol)
            payload = await self._get(
                {
                    "function": "CURRENCY_EXCHANGE_RATE",
                    "from_currency": from_symbol,
                    "to_currency": to_symbol,
                }
            )
            rate = payload.get("Realtime Currency Exchange Rate")
            if not isinstance(rate, dict) or "5. Exchange Rate" not in rate:
                raise ProviderError("Alpha Vantage returned no forex quote")
            price = float(rate["5. Exchange Rate"])
            timestamp = datetime.now(timezone.utc)
            return MarketSnapshot(
                symbol=symbol.upper(),
                asset_class=asset_class,
                price=price,
                timestamp=timestamp,
                source=self.name,
                status=DataStatus.LIVE,
                latency_ms=payload.get("_latency_ms"),
            )

        if asset_class == AssetClass.CRYPTO:
            base = symbol.replace("/", "").replace("_", "").upper()
            if len(base) < 6:
                raise ProviderError("Unsupported Alpha Vantage crypto symbol")
            crypto = base[:-3]
            market = base[-3:]
            payload = await self._get(
                {
                    "function": "CURRENCY_EXCHANGE_RATE",
                    "from_currency": crypto,
                    "to_currency": market,
                }
            )
            rate = payload.get("Realtime Currency Exchange Rate")
            if not isinstance(rate, dict) or "5. Exchange Rate" not in rate:
                raise ProviderError("Alpha Vantage returned no crypto quote")
            price = float(rate["5. Exchange Rate"])
            return MarketSnapshot(
                symbol=symbol.upper(),
                asset_class=asset_class,
                price=price,
                timestamp=datetime.now(timezone.utc),
                source=self.name,
                status=DataStatus.LIVE,
                latency_ms=payload.get("_latency_ms"),
            )

        payload = await self._get({"function": "GLOBAL_QUOTE", "symbol": symbol.upper()})
        quote = payload.get("Global Quote")
        if not isinstance(quote, dict) or not quote.get("05. price"):
            raise ProviderError("Alpha Vantage returned no stock quote")
        return MarketSnapshot(
            symbol=symbol.upper(),
            asset_class=asset_class,
            price=float(quote["05. price"]),
            timestamp=datetime.now(timezone.utc),
            source=self.name,
            status=DataStatus.STALE,
            latency_ms=payload.get("_latency_ms"),
        )

    async def ohlcv(
        self,
        symbol: str,
        interval: str,
        outputsize: int = 200,
    ) -> list[OHLCVBar]:
        normalized = interval.strip().lower()
        if normalized == "1day":
            function = "TIME_SERIES_DAILY"
            series_name = "Time Series (Daily)"
            params = {"function": function, "symbol": symbol.upper(), "outputsize": "compact"}
        elif normalized == "1week":
            function = "TIME_SERIES_WEEKLY"
            series_name = "Weekly Time Series"
            params = {"function": function, "symbol": symbol.upper()}
        elif normalized == "1h":
            function = "TIME_SERIES_INTRADAY"
            series_name = "Time Series (60min)"
            params = {
                "function": function,
                "symbol": symbol.upper(),
                "interval": "60min",
                "outputsize": "compact",
            }
        else:
            raise ProviderError(f"Alpha Vantage does not support interval {normalized}")

        payload = await self._get(params)
        values = payload.get(series_name)
        if not isinstance(values, dict):
            raise ProviderError(f"Alpha Vantage returned no {series_name} data")

        bars: list[OHLCVBar] = []
        for raw_timestamp, row in values.items():
            if not isinstance(row, dict):
                continue
            try:
                timestamp = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                bars.append(
                    OHLCVBar(
                        timestamp=timestamp,
                        open=float(row.get("1. open")),
                        high=float(row.get("2. high")),
                        low=float(row.get("3. low")),
                        close=float(row.get("4. close")),
                        volume=(
                            float(row.get("5. volume"))
                            if row.get("5. volume") not in (None, "")
                            else None
                        ),
                    )
                )
            except (TypeError, ValueError):
                continue

        if not bars:
            raise ProviderError("Alpha Vantage returned no valid OHLCV bars")
        return sorted(bars, key=lambda bar: bar.timestamp)[-outputsize:]
