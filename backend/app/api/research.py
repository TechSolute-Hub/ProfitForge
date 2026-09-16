from fastapi import APIRouter, Depends, HTTPException, Query
from app.core.config import Settings, get_settings
from app.models.market import AssetClass, DataStatus, ResearchResult
from app.services.market import MarketService
from app.services.analysis import analyze_bars

router = APIRouter(prefix="/research", tags=["research"])
DISCLAIMER = "This tool provides market research and analysis assistance only. It is **not** financial advice, a recommendation to buy or sell, or a substitute for professional advice. Trading and investing involve substantial risk of loss. Past performance is not indicative of future results. Users are solely responsible for their own decisions."


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
        raise HTTPException(status_code=503, detail={"message": "Current market data is unavailable", "snapshot": snapshot.model_dump(mode="json")})
    try:
        bars = await service.bars(symbol, timeframe, 200)
        metrics = analyze_bars(bars)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Market history validation/analysis failed: {exc}") from exc
    direction = "higher" if metrics["bias"] == "BULLISH" else "lower"
    return ResearchResult(
        symbol=symbol.upper(), asset_class=asset_class, snapshot=snapshot, timeframe=timeframe,
        bias=metrics["bias"], score=metrics["score"], confidence=metrics["confidence"], regime=metrics["regime"],
        factors=metrics["factors"], bars_used=len(bars),
        explanation=[
            f"EMA20 is {'above' if metrics['ema20'] > metrics['ema50'] else 'below'} EMA50.",
            f"RSI(14) is {metrics['rsi']:.1f}.",
            f"Recent structure is consistent with {direction} price pressure.",
        ],
        invalidation=f"A sustained break against the current structure would invalidate the {metrics['bias'].lower()} bias.",
        alternative_scenario="If momentum and structure lose alignment, the market may transition toward a neutral/range condition.",
        disclaimer=DISCLAIMER,
    )
