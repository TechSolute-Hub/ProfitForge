from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

import httpx

from app.core.config import Settings
from app.data.providers.twelve_data import ProviderError
from app.models.context import EconomicContext, EconomicEvent, NewsItem, NewsSentimentSnapshot
from app.models.market import AssetClass


class AlphaVantageContextProvider:
    """News/sentiment and earnings-context adapter using Alpha Vantage."""

    name = "Alpha Vantage"

    def __init__(self, settings: Settings):
        self.settings = settings

    def _require_key(self) -> None:
        if not self.settings.alpha_vantage_api_key:
            raise ProviderError("Alpha Vantage API key is not configured")

    async def _get_json(self, params: dict[str, str]) -> dict[str, object]:
        self._require_key()
        try:
            async with httpx.AsyncClient(timeout=self.settings.provider_request_timeout_seconds) as client:
                response = await client.get(
                    self.settings.alpha_vantage_base_url,
                    params={**params, "apikey": self.settings.alpha_vantage_api_key},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError("Alpha Vantage context request failed") from exc
        if not isinstance(payload, dict):
            raise ProviderError("Alpha Vantage returned an invalid context response")
        if "Note" in payload or "Information" in payload or "Error Message" in payload:
            raise ProviderError(str(payload.get("Note") or payload.get("Information") or payload.get("Error Message")))
        return payload

    async def _get_text(self, params: dict[str, str]) -> str:
        self._require_key()
        try:
            async with httpx.AsyncClient(timeout=self.settings.provider_request_timeout_seconds) as client:
                response = await client.get(
                    self.settings.alpha_vantage_base_url,
                    params={**params, "apikey": self.settings.alpha_vantage_api_key},
                )
                response.raise_for_status()
                return response.text
        except httpx.HTTPError as exc:
            raise ProviderError("Alpha Vantage calendar request failed") from exc

    @staticmethod
    def _ticker(symbol: str, asset_class: AssetClass) -> str:
        normalized = symbol.replace("/", "").replace("_", "").upper()
        if asset_class == AssetClass.STOCK:
            return normalized
        if asset_class == AssetClass.CRYPTO:
            return f"CRYPTO:{normalized[:-4] if normalized.endswith('USDT') else normalized}"
        if len(normalized) == 6:
            return f"FOREX:{normalized[:3]}"
        raise ProviderError("Unsupported forex symbol for news sentiment")

    async def news(self, symbol: str, asset_class: AssetClass, limit: int = 8) -> NewsSentimentSnapshot:
        payload = await self._get_json(
            {
                "function": "NEWS_SENTIMENT",
                "tickers": self._ticker(symbol, asset_class),
                "sort": "LATEST",
                "limit": str(max(1, min(limit, 50))),
            }
        )
        feed = payload.get("feed")
        if not isinstance(feed, list):
            raise ProviderError("Alpha Vantage returned no news feed")

        items: list[NewsItem] = []
        weighted_scores: list[tuple[float, float]] = []
        for raw in feed:
            if not isinstance(raw, dict):
                continue
            try:
                published = datetime.strptime(str(raw["time_published"]), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
                sentiment = float(raw.get("overall_sentiment_score", 0.0))
                relevance = 0.0
                ticker_sentiments = raw.get("ticker_sentiment", [])
                if isinstance(ticker_sentiments, list):
                    for ticker in ticker_sentiments:
                        if isinstance(ticker, dict) and str(ticker.get("ticker", "")).upper() == self._ticker(symbol, asset_class):
                            relevance = max(0.0, min(1.0, float(ticker.get("relevance_score", 0.0))))
                            sentiment = float(ticker.get("ticker_sentiment_score", sentiment))
                            break
                relevance = relevance or 0.5
                items.append(
                    NewsItem(
                        title=str(raw.get("title", "Untitled")),
                        url=str(raw.get("url", "")),
                        source=str(raw.get("source", self.name)),
                        published_at=published,
                        sentiment_score=max(-1.0, min(1.0, sentiment)),
                        sentiment_label=str(raw.get("overall_sentiment_label", "Neutral")),
                        relevance=relevance,
                    )
                )
                weighted_scores.append((sentiment, relevance))
            except (KeyError, TypeError, ValueError):
                continue

        if not items:
            raise ProviderError("Alpha Vantage returned no parseable news items")
        denominator = sum(weight for _, weight in weighted_scores) or 1.0
        score = max(-100.0, min(100.0, sum(score * weight for score, weight in weighted_scores) / denominator * 100.0))
        label = "Bullish" if score >= 20 else "Bearish" if score <= -20 else "Neutral"
        return NewsSentimentSnapshot(
            symbol=symbol.upper(),
            asset_class=asset_class,
            score=score,
            label=label,
            article_count=len(items),
            source=self.name,
            observed_at=datetime.now(timezone.utc),
            items=items,
        )

    async def earnings(self, symbol: str) -> EconomicContext:
        raw_csv = await self._get_text(
            {"function": "EARNINGS_CALENDAR", "symbol": symbol.upper(), "horizon": "3month"}
        )
        reader = csv.DictReader(io.StringIO(raw_csv))
        events: list[EconomicEvent] = []
        for row in reader:
            date_text = row.get("reportDate") or row.get("report_date")
            if not date_text:
                continue
            try:
                event_date = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            events.append(
                EconomicEvent(
                    symbol=symbol.upper(),
                    event_type="earnings",
                    event_date=event_date,
                    description=f"Expected earnings for {symbol.upper()}",
                    importance="high",
                    source=self.name,
                )
            )
        return EconomicContext(
            symbol=symbol.upper(),
            asset_class=AssetClass.STOCK,
            events=events[:8],
            source=self.name,
            observed_at=datetime.now(timezone.utc),
            available=True,
        )
