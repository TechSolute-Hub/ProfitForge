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
    """RLS-scoped repository using the authenticated user's Supabase JWT.

    The publishable key identifies the application. The user's access token is
    forwarded as the Authorization header, so Postgres RLS remains the final
    authorization boundary. No service-role/secret key is used here.
    """

    def __init__(self, settings: Settings, access_token: str):
        if not settings.supabase_url or not settings.supabase_publishable_key:
            raise SupabaseRepositoryError("Supabase is not configured")
        if not access_token:
            raise SupabaseRepositoryError("Missing Supabase access token")

        self.base_url = settings.supabase_url.rstrip("/")
        self.api_url = f"{self.base_url}/rest/v1"
        self.access_token = access_token
        self.timeout = settings.supabase_request_timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self._publishable_key,
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    @property
    def _publishable_key(self) -> str:
        # Kept as a lazy property so the token itself is never mixed into
        # configuration or logged alongside the application credential.
        return self._settings.supabase_publishable_key if hasattr(self, "_settings") else ""

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

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method,
                f"{self.api_url}/{path.lstrip('/')}",
                headers=headers,
                params=params,
                json=json,
            )

        if response.status_code >= 400:
            raise SupabaseRepositoryError(
                f"Supabase request failed with HTTP {response.status_code}"
            )

        if not response.content:
            return []
        payload = response.json()
        return payload if isinstance(payload, list) else [payload]

    def _bind_settings(self, settings: Settings) -> None:
        self._settings = settings

    async def ensure_default_watchlist(self, user_id: UUID) -> UUID:
        rows = await self._request(
            "GET",
            "watchlists",
            params={"select": "id", "user_id": f"eq.{user_id}", "name": "eq.Default", "limit": "1"},
        )
        if rows:
            return UUID(str(rows[0]["id"]))

        created = await self._request(
            "POST",
            "watchlists",
            json={"user_id": str(user_id), "name": "Default"},
            prefer="return=representation",
        )
        if not created:
            raise SupabaseRepositoryError("Supabase did not return the default watchlist")
        return UUID(str(created[0]["id"]))

    async def add_watchlist_item(self, item: WatchlistItem) -> None:
        watchlist_id = item.watchlist_id or await self.ensure_default_watchlist(item.user_id)
        payload = {
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
            watchlist_id = str(watchlist["id"])
            await self._request(
                "DELETE",
                "watchlist_items",
                params={
                    "watchlist_id": f"eq.{watchlist_id}",
                    "symbol": f"eq.{symbol.strip().upper()}",
                    "asset_class": f"eq.{asset_class.value}",
                },
            )

    async def save_analysis(self, analysis: SavedAnalysis) -> None:
        payload = {
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

    async def record_history(self, record: ResearchHistoryRecord) -> None:
        result = dict(record.result)
        result.setdefault("asset_class", record.asset_class.value)
        result.setdefault("timeframe", record.timeframe)
        result.setdefault("score", record.score)
        result.setdefault("confidence", record.confidence)
        result.setdefault("bias", record.bias)
        result.setdefault("regime", record.regime)

        payload = {
            "user_id": str(record.user_id),
            "record_type": "REPORT",
            "symbol": record.symbol.strip().upper(),
            "title": f"{record.symbol.strip().upper()} {record.timeframe} research",
            "payload": result,
            "saved": False,
            "created_at": record.observed_at.astimezone(timezone.utc).isoformat(),
            "updated_at": record.observed_at.astimezone(timezone.utc).isoformat(),
        }
        await self._request("POST", "research_history", json=payload)


def create_supabase_repository(settings: Settings, access_token: str) -> SupabaseRepository:
    repository = SupabaseRepository(settings, access_token)
    repository._bind_settings(settings)
    return repository
