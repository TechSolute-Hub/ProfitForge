from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.core.config import Settings
from app.learning.models import ModelVersion, VersionStatus
from app.learning.validation import SignalOutcomeObservation


class ModelPersistenceError(RuntimeError):
    """Raised when persistent learning state cannot be read or written."""


class SupabaseModelRepository:
    """Server-side repository for global model versions and signal outcomes."""

    def __init__(self, settings: Settings):
        if not settings.supabase_url or not settings.supabase_secret_key:
            raise ModelPersistenceError("Server-side Supabase model persistence is not configured")
        self.settings = settings
        self.api_url = f"{settings.supabase_url.rstrip('/')}/rest/v1"

    def _headers(self) -> dict[str, str]:
        return {"apikey": self.settings.supabase_secret_key, "Authorization": f"Bearer {self.settings.supabase_secret_key}", "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, *, params: dict[str, str] | None = None, payload: object | None = None, prefer: str | None = None) -> list[dict[str, object]]:
        headers = self._headers()
        if prefer:
            headers["Prefer"] = prefer
        try:
            async with httpx.AsyncClient(timeout=self.settings.supabase_request_timeout_seconds) as client:
                response = await client.request(method, f"{self.api_url}/{path.lstrip('/')}", headers=headers, params=params, json=payload)
        except httpx.HTTPError as exc:
            raise ModelPersistenceError("Supabase model request could not be completed") from exc
        if response.status_code >= 400:
            raise ModelPersistenceError(f"Supabase model request failed with HTTP {response.status_code}")
        if not response.content:
            return []
        data = response.json()
        return data if isinstance(data, list) else [data]

    async def active_model(self, model_family: str) -> ModelVersion | None:
        rows = await self._request("GET", "model_versions", params={"select":"*", "model_family":f"eq.{model_family}", "status":"eq.ACTIVE", "limit":"1"})
        return _model_from_row(rows[0]) if rows else None

    async def get_model(self, version_id: str) -> ModelVersion | None:
        rows = await self._request("GET", "model_versions", params={"select":"*", "version_id":f"eq.{version_id}", "limit":"1"})
        return _model_from_row(rows[0]) if rows else None

    async def create_candidate(self, version: ModelVersion) -> ModelVersion:
        payload = {"model_family":version.model_family,"version_id":version.version_id,"status":version.status.value,"weights":version.weights,"parent_version_id":version.parent_version_id,"training_observations":version.training_observations,"oos_observations":version.oos_observations,"validation_metrics":version.validation_metrics,"artifact_checksum":version.artifact_checksum,"created_at":version.created_at.astimezone(timezone.utc).isoformat()}
        rows = await self._request("POST", "model_versions", payload=payload, prefer="return=representation")
        if not rows:
            raise ModelPersistenceError("Supabase did not return the model candidate")
        return _model_from_row(rows[0])

    async def update_validation(self, version_id: str, oos_observations: int, metrics: dict[str, float]) -> None:
        await self._request("PATCH", "model_versions", params={"version_id":f"eq.{version_id}"}, payload={"oos_observations":oos_observations,"validation_metrics":metrics})

    async def mark_validated(self, version_id: str) -> ModelVersion:
        rows = await self._request("PATCH", "model_versions", params={"version_id":f"eq.{version_id}","status":"eq.DRAFT"}, payload={"status":VersionStatus.VALIDATED.value}, prefer="return=representation")
        if not rows:
            raise ModelPersistenceError("Only draft model versions can be validated")
        return _model_from_row(rows[0])

    async def activate(self, version_id: str) -> ModelVersion:
        candidate = await self.get_model(version_id)
        if candidate is None or candidate.status != VersionStatus.VALIDATED:
            raise ModelPersistenceError("Only validated model versions can be activated")
        await self._request("PATCH", "model_versions", params={"model_family":f"eq.{candidate.model_family}","status":"eq.ACTIVE"}, payload={"status":VersionStatus.ROLLED_BACK.value,"rolled_back_at":datetime.now(timezone.utc).isoformat()})
        rows = await self._request("PATCH", "model_versions", params={"version_id":f"eq.{version_id}","status":"eq.VALIDATED"}, payload={"status":VersionStatus.ACTIVE.value,"activated_at":datetime.now(timezone.utc).isoformat()}, prefer="return=representation")
        if not rows:
            raise ModelPersistenceError("Model version activation failed")
        return _model_from_row(rows[0])

    async def signal_outcomes(self, limit: int = 5000) -> list[SignalOutcomeObservation]:
        rows = await self._request("GET", "signal_outcomes", params={"select":"signal_id,signal_time,factor_scores,outcome_return_pct,regime","outcome_return_pct":"not.is.null","order":"signal_time.asc","limit":str(limit)})
        result: list[SignalOutcomeObservation] = []
        for row in rows:
            scores, outcome = row.get("factor_scores"), row.get("outcome_return_pct")
            if not isinstance(scores, dict) or not isinstance(outcome, (int, float)):
                continue
            result.append(SignalOutcomeObservation(str(row["signal_id"]),str(row["signal_time"]),{str(k):float(v) for k,v in scores.items() if isinstance(v,(int,float))},float(outcome),str(row.get("regime") or "UNKNOWN")))
        return result

    async def record_signal_outcome(self, payload: dict[str, object]) -> None:
        await self._request("POST", "signal_outcomes", payload=payload, prefer="resolution=merge-duplicates,return=minimal")


def _model_from_row(row: dict[str, object]) -> ModelVersion:
    created = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
    return ModelVersion(version_id=str(row["version_id"]),model_family=str(row["model_family"]),created_at=created,status=VersionStatus(str(row["status"])),weights={str(k):float(v) for k,v in dict(row["weights"]).items()},parent_version_id=str(row["parent_version_id"]) if row.get("parent_version_id") else None,training_observations=int(row["training_observations"]),oos_observations=int(row["oos_observations"]),validation_metrics={str(k):float(v) for k,v in dict(row["validation_metrics"]).items()},artifact_checksum=str(row["artifact_checksum"]))
