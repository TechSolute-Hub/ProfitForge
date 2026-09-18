import asyncio
from functools import lru_cache
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from app.analysis.engine import analyze_multi_timeframe
from app.core.config import Settings, get_settings
from app.learning.service import LearningService
from app.models.market import AssetClass, DataStatus, ResearchResult
from app.services.context import MarketContextService, get_market_context_service
from app.services.market import MarketService, get_market_service

router = APIRouter(prefix="/research", tags=["research"])
DISCLAIMER = "This tool provides market research and analysis assistance only. It is **not** financial advice, a recommendation to buy or sell, or a substitute for professional advice. Trading and investing involve substantial risk of loss. Past performance is not indicative of future results. Users are solely responsible for their own decisions."
TIMEFRAMES = ("1h", "4h", "1day", "1week")
BARS_PER_TIMEFRAME = 250

@lru_cache(maxsize=1)
def get_learning_service() -> LearningService:
    return LearningService(get_settings())

async def _fetch_timeframe(service: MarketService, symbol: str, timeframe: str) -> tuple[str, list | None, str | None]:
    try:
        return timeframe, await service.bars(symbol, timeframe, BARS_PER_TIMEFRAME), None
    except Exception:
        return timeframe, None, "data_unavailable"

@router.get("/analyze", response_model=ResearchResult)
async def analyze(symbol: str = Query(min_length=1, max_length=30), asset_class: AssetClass = AssetClass.STOCK, timeframe: str = Query(default="1day", pattern="^(1h|4h|1day|1week)$"), service: MarketService = Depends(get_market_service), context_service: MarketContextService = Depends(get_market_context_service), learning_service: LearningService = Depends(get_learning_service)) -> ResearchResult:
    snapshot = await service.quote(symbol, asset_class)
    if snapshot.status != DataStatus.LIVE:
        raise HTTPException(status_code=503, detail={"message":"Current market data is unavailable","snapshot":snapshot.model_dump(mode="json")})
    results = await asyncio.gather(*(_fetch_timeframe(service, symbol, current) for current in TIMEFRAMES))
    bars_by_timeframe = {current: bars for current, bars, _ in results if bars is not None}
    failures = {current: error for current, bars, error in results if bars is None and error is not None}
    if timeframe not in bars_by_timeframe:
        raise HTTPException(status_code=422, detail="Requested timeframe could not be analyzed because its market history is unavailable.")
    context = await context_service.context(symbol, asset_class)
    news_score = context.news.score if context.news else None
    news_reason = f"{context.news.article_count} recent articles; weighted sentiment is {context.news.label.lower()} ({context.news.score:.1f})." if context.news else "News/sentiment data is unavailable; no value is fabricated."
    factor_weights, model_version = await learning_service.active_weights()
    try:
        intelligence = analyze_multi_timeframe(bars_by_timeframe, primary=timeframe, news_score=news_score, news_reason=news_reason, factor_weights=factor_weights)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"Market history validation/analysis failed: {exc}") from exc
    primary = intelligence["timeframes"][timeframe]
    direction = "higher" if intelligence["bias"] == "BULLISH" else "lower" if intelligence["bias"] == "BEARISH" else "sideways"
    explanations = [f"Primary timeframe ({timeframe}) bias is {primary['bias']} with a score of {primary['score']}.",f"EMA20/50/200 alignment: {primary['indicators']['ema20']:.4g} / {primary['indicators']['ema50']:.4g} / {primary['indicators']['ema200']:.4g}.",f"RSI(14) is {primary['indicators']['rsi14']:.1f}; MACD histogram is {primary['indicators']['macd_histogram']:.4g}.",f"Confirmed structure is {primary['structure']['high_sequence']}/{primary['structure']['low_sequence']} with {primary['structure']['bias']} structural bias.",f"Multi-timeframe alignment is {intelligence['alignment']}%, supporting {direction} price pressure.",f"Scoring model: {model_version or 'BASELINE'}.",f"Active factor weights: {', '.join(f'{key}={value:.2f}' for key,value in factor_weights.items())}."]
    explanations.append(f"News context: {context.news.label.lower()} sentiment from {context.news.article_count} recent relevant articles." if context.news else "News context is unavailable; it is excluded from the score rather than inferred.")
    if context.economic and context.economic.events:
        explanations.append(f"Economic context: {len(context.economic.events)} upcoming earnings event(s) were found for this stock.")
    if failures:
        explanations.append(f"Unavailable timeframes: {', '.join(sorted(failures))}; missing data is not fabricated.")
    return ResearchResult(signal_id=uuid4(),model_version=model_version or "BASELINE",factor_weights=factor_weights,symbol=symbol.upper(),asset_class=asset_class,timeframe=timeframe,snapshot=snapshot,bias=intelligence["bias"],score=intelligence["score"],confidence=intelligence["confidence"],regime=primary["regime"],factors=primary["factors"],factor_contributions=primary["contributions"],indicators=primary["indicators"],structure=primary["structure"],mtf_score=intelligence["mtf_score"],mtf_alignment=intelligence["alignment"],timeframe_analysis=intelligence["timeframes"],data_quality=primary["data_quality"],unavailable_factors=primary["unavailable_factors"],news_sentiment=context.news,economic_context=context.economic,explanation=explanations,invalidation=f"A confirmed break against the {timeframe} swing structure would weaken or invalidate the current {intelligence['bias'].lower()} bias.",alternative_scenario="If higher and lower timeframes lose alignment, the market may transition toward a neutral/range condition.",bars_used=primary["bars_used"],disclaimer=DISCLAIMER)
