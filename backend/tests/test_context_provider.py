from datetime import datetime, timezone

import pytest

from app.core.config import Settings
from app.data.providers.alpha_vantage_context import AlphaVantageContextProvider
from app.models.market import AssetClass


@pytest.mark.asyncio
async def test_news_parser_uses_ticker_specific_sentiment() -> None:
    provider = AlphaVantageContextProvider(Settings(alpha_vantage_api_key="test"))

    async def fake_get(_: dict[str, str]) -> dict[str, object]:
        return {
            "feed": [
                {
                    "title": "Positive AAPL report",
                    "url": "https://example.com/aapl",
                    "source": "Example",
                    "time_published": "20260917T120000",
                    "overall_sentiment_score": "0.10",
                    "overall_sentiment_label": "Neutral",
                    "ticker_sentiment": [
                        {
                            "ticker": "AAPL",
                            "relevance_score": "0.90",
                            "ticker_sentiment_score": "0.60",
                        }
                    ],
                }
            ]
        }

    provider._get_json = fake_get  # type: ignore[method-assign]
    snapshot = await provider.news("AAPL", AssetClass.STOCK, limit=8)

    assert snapshot.article_count == 1
    assert snapshot.score == pytest.approx(60.0)
    assert snapshot.label == "Bullish"
    assert snapshot.items[0].published_at == datetime(2026, 9, 17, 12, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_earnings_parser_handles_csv() -> None:
    provider = AlphaVantageContextProvider(Settings(alpha_vantage_api_key="test"))

    async def fake_get(_: dict[str, str]) -> str:
        return "symbol,name,reportDate\nAAPL,Apple,2026-10-29\n"

    provider._get_text = fake_get  # type: ignore[method-assign]
    context = await provider.earnings("AAPL")

    assert len(context.events) == 1
    assert context.events[0].event_type == "earnings"
    assert context.events[0].event_date.year == 2026
