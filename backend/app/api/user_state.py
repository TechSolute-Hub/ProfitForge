from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.models.market import AssetClass, ResearchResult
from app.persistence.repository import ResearchHistoryRecord, SavedAnalysis, WatchlistItem
from app.persistence.supabase_repository import (
    SupabaseRepository,
    SupabaseRepositoryError,
    create_supabase_repository,
)

router = APIRouter(prefix="/user-state", tags=["user-state"])


class AuthenticatedUser(BaseModel):
    id: UUID
    email: str | None = None


class WatchlistRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    asset_class: AssetClass
    notes: str | None = Field(default=None, max_length=2000)
    watchlist_id: UUID | None = None


class SaveAnalysisRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    result: ResearchResult


class SignalOutcomeRequest(BaseModel):
    signal_id: UUID
    symbol: str = Field(min_length=1, max_length=32)
    timeframe: str = Field(pattern="^(1h|4h|1day|1week)$")
    signal_time: str
    outcome_time: str | None = None
    score: int = Field(ge=-100, le=100)
    bias: str
    regime: str
    factor_scores: dict[str, float]
    factor_contributions: dict[str, float] = Field(default_factory=dict)
    outcome_return_pct: float | None = None
    outcome_label: str | None = None
    horizon_bars: int = Field(ge=1, le=10000)


async def get_current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> AuthenticatedUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")

    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise HTTPException(status_code=503, detail="User-state persistence is not configured")

    try:
        async with httpx.AsyncClient(timeout=settings.supabase_request_timeout_seconds) as client:
            response = await client.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
                headers={
                    "apikey": settings.supabase_publishable_key,
                    "Authorization": f"Bearer {token}",
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail="Authentication service unavailable") from exc

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    try:
        payload = response.json()
        return AuthenticatedUser(id=UUID(str(payload["id"])), email=payload.get("email"))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication response") from exc


def repository(
    authorization: str | None,
    settings: Settings,
) -> SupabaseRepository:
    token = authorization[7:].strip() if authorization else ""
    try:
        return create_supabase_repository(settings, token)
    except SupabaseRepositoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/me")
async def me(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    return user


@router.get("/watchlists")
async def get_watchlists(
    user: AuthenticatedUser = Depends(get_current_user),
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, object]]:
    repo = repository(authorization, settings)
    try:
        return await repo.list_watchlists(user.id)
    except SupabaseRepositoryError as exc:
        raise HTTPException(status_code=502, detail="Could not load watchlists") from exc


@router.post("/watchlists/items", status_code=204)
async def add_watchlist_item(
    request: WatchlistRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    repo = repository(authorization, settings)
    try:
        await repo.add_watchlist_item(
            WatchlistItem(
                user_id=user.id,
                symbol=request.symbol,
                asset_class=request.asset_class,
                notes=request.notes,
                watchlist_id=request.watchlist_id,
            )
        )
    except SupabaseRepositoryError as exc:
        raise HTTPException(status_code=502, detail="Could not update watchlist") from exc


@router.delete("/watchlists/items", status_code=204)
async def delete_watchlist_item(
    symbol: str,
    asset_class: AssetClass,
    user: AuthenticatedUser = Depends(get_current_user),
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    repo = repository(authorization, settings)
    try:
        await repo.remove_watchlist_item(user.id, symbol, asset_class)
    except SupabaseRepositoryError as exc:
        raise HTTPException(status_code=502, detail="Could not update watchlist") from exc


@router.post("/history", status_code=204)
async def record_history(
    result: ResearchResult,
    user: AuthenticatedUser = Depends(get_current_user),
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    repo = repository(authorization, settings)
    try:
        await repo.record_history(
            ResearchHistoryRecord(
                user_id=user.id,
                symbol=result.symbol,
                asset_class=result.asset_class,
                timeframe=result.timeframe,
                score=result.score,
                confidence=result.confidence,
                bias=result.bias,
                regime=result.regime,
                result=result.model_dump(mode="json"),
                observed_at=result.snapshot.timestamp,
            )
        )
    except SupabaseRepositoryError as exc:
        raise HTTPException(status_code=502, detail="Could not save research history") from exc


@router.get("/saved-analyses")
async def get_saved_analyses(
    user: AuthenticatedUser = Depends(get_current_user),
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> list[dict[str, object]]:
    repo = repository(authorization, settings)
    try:
        return await repo.list_saved_analyses(user.id)
    except SupabaseRepositoryError as exc:
        raise HTTPException(status_code=502, detail="Could not load saved analyses") from exc


@router.post("/saved-analyses", status_code=204)
async def save_analysis(
    request: SaveAnalysisRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    repo = repository(authorization, settings)
    try:
        await repo.save_analysis(
            SavedAnalysis(
                user_id=user.id,
                name=request.name,
                symbol=request.result.symbol,
                asset_class=request.result.asset_class,
                timeframe=request.result.timeframe,
                result=request.result.model_dump(mode="json"),
            )
        )
    except SupabaseRepositoryError as exc:
        raise HTTPException(status_code=502, detail="Could not save analysis") from exc


@router.post("/signal-outcomes", status_code=204)
async def record_signal_outcome(
    request: SignalOutcomeRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    repo = repository(authorization, settings)
    payload = request.model_dump(mode="json")
    payload["user_id"] = str(user.id)
    try:
        await repo.record_signal_outcome(payload)
    except SupabaseRepositoryError as exc:
        raise HTTPException(status_code=502, detail="Could not save signal outcome") from exc
