from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass
class _Entry(Generic[T]):
    value: T
    expires_at: float


class AsyncTTLCache(Generic[T]):
    """Small process-local async cache with per-key stampede protection."""

    def __init__(self, default_ttl_seconds: int = 30, max_entries: int = 512) -> None:
        if default_ttl_seconds < 0:
            raise ValueError("default_ttl_seconds must be non-negative")
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self.default_ttl_seconds = default_ttl_seconds
        self.max_entries = max_entries
        self._entries: dict[str, _Entry[T]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, key: str) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [key for key, entry in self._entries.items() if entry.expires_at <= now]
        for key in expired:
            self._entries.pop(key, None)
            self._locks.pop(key, None)

        while len(self._entries) > self.max_entries:
            oldest_key = min(self._entries, key=lambda item: self._entries[item].expires_at)
            self._entries.pop(oldest_key, None)
            self._locks.pop(oldest_key, None)

    async def get(self, key: str) -> T | None:
        self._purge_expired()
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= time.monotonic():
            self._entries.pop(key, None)
            return None
        return entry.value

    async def set(self, key: str, value: T, ttl_seconds: int | None = None) -> None:
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            return
        self._entries[key] = _Entry(value=value, expires_at=time.monotonic() + ttl)
        self._purge_expired()

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl_seconds: int | None = None,
    ) -> T:
        cached = await self.get(key)
        if cached is not None:
            return cached

        async with self._lock_for(key):
            cached = await self.get(key)
            if cached is not None:
                return cached
            value = await factory()
            await self.set(key, value, ttl_seconds)
            return value

    async def clear(self) -> None:
        self._entries.clear()
        self._locks.clear()
