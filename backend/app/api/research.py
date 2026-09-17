import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query

from app.analysis.engine import analyze_multi_timeframe
from app.models.market import AssetClass, DataStatus, ResearchResult
from app.services.market import MarketService, get_market_service

router = APIRouter(prefix="/research", tags=["research"])
DISCLAIMER = "This tool provides market research and analysis assistance only. It is **not** financial advice, a recommendation to buy or sell, or a substitute for professional advice. Trading and investing involve substantial risk of loss. Past performance is not indicative of future results. Users are solely responsible for their own decisions."
TIMEFRAMES = ("1h", "4h", "1day", "1week")
BARS_PER_TIMEFRAME = 250


async def _fetch_timeframe(
    service: MarketService,
    symbol: str,
    timeframe: str,
) -> tuple[str, list | None, str | None]:
    try:
        bars = await service.bars(symbol, timeframe, BARS_PER_TIMEFRAME)
        return timeframe, bars, None
    except Exception:
        # Provider details stay server-side; the API exposes only a stable category.
        return timeframe, None, "data_unavailable"


@router.get("/analyze", response_model=ResearchResult)
async def analyze(
    symbol: str = Query(min_length=1, max_length=30),
    asset_class: AssetClass = AssetClass.STOCK,
    timeframe: str = Query(default="1day", pattern="^(1h|4h|1day|1week)$"),
    service: MarketService = Depends(get_market_service),
) -> ResearchResult:
    snapshot = await service.quote(symbol, asset_class)
    if snapshot.status != DataStatus.LIVE:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Current market data is unavailable",
                "snapshot": snapshot.model_dump(mode="json"),
            },
        )

    results = await asyncio.gather(
        *(_fetch_timeframe(service, symbol, current) for current in TIMEFRAMES)
    )
    bars_by_timeframe = {
        current: bars for current, bars, error in results if bars is not None
    }
    failures = {
        current: error
        for current, bars, error in results
        if bars is None and error is not None
    }

    if timeframe not in bars_by_timeframe:
        raise HTTPException(
            status_code=422,
            detail="Requested timeframe could not be analyzed because its market history is unavailable.",
        )

    try:
        intelligence = analyze_multi_timeframe(bars_by_timeframe, primary=timeframe)
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Market history validation/analysis failed: {exc}",
        ) from exc

    primary = intelligence["timeframes"][timeframe]
    direction = (
        "higher"
        if intelligence["bias"] == "BULLISH"
        else "lower"
        if intelligence["bias"] == "BEARISH"
        else "sideways"
    )
    explanations = [
        f"Primary timeframe ({timeframe}) bias is {primary['bias']} with a score of {primary['score']}.",
        f"EMA20/50/200 alignment: {primary['indicators']['ema20']:.4g} / {primary['indicators']['ema50']:.4g} / {primary['indicators']['ema200']:.4g}.",
        f"RSI(14) is {primary['indicators']['rsi14']:.1f}; MACD histogram is {primary['indicators']['macd_histogram']:.4g}.",
        f"Confirmed structure is {primary['structure']['high_sequence']}/{primary['structure']['low_sequence']} with {primary['structure']['bias']} structural bias.",
        f"Multi-timeframe alignment is {intelligence['alignment']}%, supporting {direction} price pressure.",
    ]
    if failures:
        explanations.append(
            f"Unavailable timeframes: {', '.join(sorted(failures))}; missing data is not fabricated."
        )

    return ResearchResult(
        symbol=symbol.upper(),
        asset_class=asset_class,
        snapshot=snapshot,
        timeframe=timeframe,
        bias=intelligence["bias"],
        score=intelligence["score"],
        confidence=intelligence["confidence"],
        regime=primary["regime"],
        factors=primary["factors"],
        factor_contributions=primary["contributions"],
        indicators=primary["indicators"],
        structure=primary["structure"],
        mtf_score=intelligence["mtf_score"],
        mtf_alignment=intelligence["alignment"],
        timeframe_analysis=intelligence["timeframes"],
        data_quality=primary["data_quality"],
        unavailable_factors=primary["unavailable_factors"],
        explanation=explanations,
        invalidation=(
            f"A confirmed break against the {timeframe} swing structure would weaken "
            f"or invalidate the current {intelligence['bias'].lower()} bias."
        ),
        alternative_scenario=(
            "If higher and lower timeframes lose alignment, the market may transition "
            "toward a neutral/range condition."
        ),
        bars_used=primary["bars_used"],
        disclaimer=DISCLAIMER,
    )
