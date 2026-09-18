from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import httpx

from app.core.config import Settings
from app.models.market import AssetClass
from app.persistence.repository import (
    ResearchHistoryRecord,
    SavedAnalysis,
    WatchlistItem,
)


class SupabaseRepositoryError(RuntimeError):
    """Raised when a user-state operation cannot be completed."""


class SupabaseRepository:
    """RLS-scoped repository using the authenticated user's Supabase JWT."""

    def __init__(self, settings: Settings, access_token: str):
        if not settings.supabase_url or not settings.supabase_publishable_key:
            raise SupabaseRepositoryError("Supabase is not configured")
        if not access_token:
            raise SupabaseRepositoryError("Missing Supabase access token")

        self.settings = settings
        self.base_url = settings.supabase_url.rstrip("/")
        self.api_url = f"{self.base_url}/rest/v1"
        self.access_token = access_token
        self.timeout = settings.supabase_request_timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.settings.supabase_publishable_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: object | None = None,
        prefer: str | None = None,
    ) -> list[dict[str, object]]:
        headers = self._headers()
        if prefer:
            headers["Prefer"] = prefer

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(
                    method,
                    f"{self.api_url}/{path.lstrip('/')}",
                    headers=headers,
                    params=params,
                    json=json,
                )
        except httpx.HTTPError as exc:
            raise SupabaseRepositoryError("Supabase request could not be completed") from exc

        if response.status_code >= 400:
            raise SupabaseRepositoryError(
                f"Supabase request failed with HTTP {response.status_code}"
            )

        if not response.content:
            return []
        payload = response.json()
        return payload if isinstance(payload, list) else [payload]

    async def ensure_default_watchlist(self, user_id: UUID) -> UUID:
        rows = await self._request(
            "POST",
            "watchlists",
            json={"user_id": str(user_id), "name": "Default"},
            prefer="resolution=merge-duplicates,return=representation",
        )
        if not rows:
            rows = await self._request(
                "GET",
                "watchlists",
                params={
                    "select": "id",
                    "user_id": f"eq.{user_id}",
                    "name": "eq.Default",
                    "limit": "1",
                },
            )
        if not rows:
            raise SupabaseRepositoryError("Supabase did not return the default watchlist")
        return UUID(str(rows[0]["id"]))

    async def list_watchlists(self, user_id: UUID) -> list[dict[str, object]]:
        return await self._request(
            "GET",
            "watchlists",
            params={
                "select": "id,name,created_at,updated_at,watchlist_items(id,symbol,asset_class,notes,created_at)",
                "user_id": f"eq.{user_id}",
                "order": "created_at.asc",
            },
        )

    async def add_watchlist_item(self, item: WatchlistItem) -> None:
        watchlist_id = item.watchlist_id or await self.ensure_default_watchlist(item.user_id)
        payload: dict[str, object] = {
            "watchlist_id": str(watchlist_id),
            "symbol": item.symbol.strip().upper(),
            "asset_class": item.asset_class.value,
        }
        if item.notes is not None:
            payload["notes"] = item.notes

        await self._request(
            "POST",
            "watchlist_items",
            json=payload,
            prefer="resolution=merge-duplicates,return=minimal",
        )

    async def remove_watchlist_item(
        self,
        user_id: UUID,
        symbol: str,
        asset_class: AssetClass,
    ) -> None:
        watchlists = await self._request(
            "GET",
            "watchlists",
            params={"select": "id", "user_id": f"eq.{user_id}"},
        )
        for watchlist in watchlists:
            await self._request(
                "DELETE",
                "watchlist_items",
                params={
                    "watchlist_id": f"eq.{watchlist['id']}",
                    "symbol": f"eq.{symbol.strip().upper()}",
                    "asset_class": f"eq.{asset_class.value}",
                },
            )

    async def save_analysis(self, analysis: SavedAnalysis) -> None:
        payload: dict[str, object] = {
            "user_id": str(analysis.user_id),
            "name": analysis.name.strip(),
            "symbol": analysis.symbol.strip().upper(),
            "asset_class": analysis.asset_class.value,
            "timeframe": analysis.timeframe,
            "result": analysis.result,
        }
        if analysis.created_at is not None:
            payload["created_at"] = analysis.created_at.astimezone(timezone.utc).isoformat()
        await self._request("POST", "saved_analyses", json=payload)

    async def list_saved_analyses(self, user_id: UUID) -> list[dict[str, object]]:
        return await self._request(
            "GET",
            "saved_analyses",
            params={
                "select": "id,name,symbol,asset_class,timeframe,result,created_at,updated_at",
                "user_id": f"eq.{user_id}",
                "order": "updated_at.desc",
            },
        )

    async def record_history(self, record: ResearchHistoryRecord) -> None:
        result = dict(record.result)
        result.setdefault("asset_class", record.asset_class.value)
        result.setdefault("timeframe", record.timeframe)
        result.setdefault("score", record.score)
        result.setdefault("confidence", record.confidence)
        result.setdefault("bias", record.bias)
        result.setdefault("regime", record.regime)

        observed_at = record.observed_at.astimezone(timezone.utc).isoformat()
        payload = {
            "user_id": str(record.user_id),
            "record_type": "REPORT",
            "symbol": record.symbol.strip().upper(),
            "title": f"{record.symbol.strip().upper()} {record.timeframe} research",
            "payload": result,
            "saved": False,
            "created_at": observed_at,
            "updated_at": observed_at,
        }
        await self._request("POST", "research_history", json=payload)

    async def record_signal_outcome(self, payload: dict[str, object]) -> None:
        """Persist a user-owned resolved signal outcome through RLS."""
        safe_payload = dict(payload)
        safe_payload["user_id"] = str(safe_payload.get("user_id"))
        await self._request(
            "POST",
            "signal_outcomes",
            json=safe_payload,
            prefer="resolution=merge-duplicates,return=minimal",
        )


def create_supabase_repository(settings: Settings, access_token: str) -> SupabaseRepository:
    return SupabaseRepository(settings, access_token)
