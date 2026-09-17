from fastapi import APIRouter, Depends, HTTPException, Query

from app.analysis.engine import analyze_multi_timeframe
from app.core.config import Settings, get_settings
from app.models.market import AssetClass, DataStatus, ResearchResult
from app.services.market import MarketService

router = APIRouter(prefix="/research", tags=["research"])
DISCLAIMER = "This tool provides market research and analysis assistance only. It is **not** financial advice, a recommendation to buy or sell, or a substitute for professional advice. Trading and investing involve substantial risk of loss. Past performance is not indicative of future results. Users are solely responsible for their own decisions."
TIMEFRAMES = ("1h", "4h", "1day", "1week")


@router.get("/analyze", response_model=ResearchResult)
async def analyze(
    symbol: str = Query(min_length=1, max_length=30),
    asset_class: AssetClass = AssetClass.STOCK,
    timeframe: str = Query(default="1day", pattern="^(1h|4h|1day|1week)$"),
    settings: Settings = Depends(get_settings),
) -> ResearchResult:
    service = MarketService(settings)
    snapshot = await service.quote(symbol, asset_class)
    if snapshot.status != DataStatus.LIVE:
        raise HTTPException(
            status_code=503,
            detail={"message": "Current market data is unavailable", "snapshot": snapshot.model_dump(mode="json")},
        )

    bars_by_timeframe: dict[str, list] = {}
    failures: dict[str, str] = {}
    for current in TIMEFRAMES:
        try:
            bars_by_timeframe[current] = await service.bars(symbol, current, 250)
        except Exception as exc:
            failures[current] = str(exc)

    if timeframe not in bars_by_timeframe:
        raise HTTPException(status_code=422, detail=f"Requested timeframe could not be analyzed: {failures.get(timeframe, 'unknown error')}")

    try:
        intelligence = analyze_multi_timeframe(bars_by_timeframe, primary=timeframe)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"Market history validation/analysis failed: {exc}") from exc

    primary = intelligence["timeframes"][timeframe]
    direction = "higher" if intelligence["bias"] == "BULLISH" else "lower" if intelligence["bias"] == "BEARISH" else "sideways"
    explanations = [
        f"Primary timeframe ({timeframe}) bias is {primary['bias']} with a score of {primary['score']}.",
        f"EMA20/50/200 alignment: {primary['indicators']['ema20']:.4g} / {primary['indicators']['ema50']:.4g} / {primary['indicators']['ema200']:.4g}.",
        f"RSI(14) is {primary['indicators']['rsi14']:.1f}; MACD histogram is {primary['indicators']['macd_histogram']:.4g}.",
        f"Confirmed structure is {primary['structure']['high_sequence']}/{primary['structure']['low_sequence']} with {primary['structure']['bias']} structural bias.",
        f"Multi-timeframe alignment is {intelligence['alignment']}%, supporting {direction} price pressure.",
    ]
    if failures:
        explanations.append(f"Unavailable timeframes: {', '.join(sorted(failures))}; missing data is not fabricated.")

    return ResearchResult(
        symbol=symbol.upper(), asset_class=asset_class, snapshot=snapshot, timeframe=timeframe,
        bias=intelligence["bias"], score=intelligence["score"], confidence=intelligence["confidence"],
        regime=primary["regime"], factors=primary["factors"], factor_contributions=primary["contributions"],
        indicators=primary["indicators"], structure=primary["structure"], mtf_score=intelligence["mtf_score"],
        mtf_alignment=intelligence["alignment"], timeframe_analysis=intelligence["timeframes"],
        data_quality=primary["data_quality"], unavailable_factors=primary["unavailable_factors"],
        explanation=explanations,
        invalidation=f"A confirmed break against the {timeframe} swing structure would weaken or invalidate the current {intelligence['bias'].lower()} bias.",
        alternative_scenario="If higher and lower timeframes lose alignment, the market may transition toward a neutral/range condition.",
        bars_used=primary["bars_used"], disclaimer=DISCLAIMER,
    )
