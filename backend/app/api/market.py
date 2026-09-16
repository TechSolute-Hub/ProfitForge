from fastapi import APIRouter, Depends, Query
from app.core.config import Settings, get_settings
from app.models.market import AssetClass, DataStatus, MarketSnapshot
from app.services.market import MarketService

router = APIRouter(prefix="/market", tags=["market"])


def get_market_service(settings: Settings = Depends(get_settings)) -> MarketService:
    return MarketService(settings)


@router.get("/quote", response_model=MarketSnapshot)
async def get_quote(
    symbol: str = Query(min_length=1, max_length=30),
    asset_class: AssetClass = AssetClass.STOCK,
    service: MarketService = Depends(get_market_service),
) -> MarketSnapshot:
    return await service.quote(symbol, asset_class)
