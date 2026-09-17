import asyncio

import pytest

from app.core.cache import AsyncTTLCache


@pytest.mark.asyncio
async def test_cache_reuses_value_within_ttl():
    cache = AsyncTTLCache[str](default_ttl_seconds=30)
    calls = 0

    async def factory() -> str:
        nonlocal calls
        calls += 1
        return "value"

    assert await cache.get_or_set("key", factory) == "value"
    assert await cache.get_or_set("key", factory) == "value"
    assert calls == 1


@pytest.mark.asyncio
async def test_cache_prevents_concurrent_stampede():
    cache = AsyncTTLCache[str](default_ttl_seconds=30)
    calls = 0

    async def factory() -> str:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return "value"

    results = await asyncio.gather(
        *(cache.get_or_set("same-key", factory) for _ in range(5))
    )
    assert results == ["value"] * 5
    assert calls == 1


@pytest.mark.asyncio
async def test_zero_ttl_does_not_retain_value():
    cache = AsyncTTLCache[str](default_ttl_seconds=0)
    calls = 0

    async def factory() -> str:
        nonlocal calls
        calls += 1
        return f"value-{calls}"

    assert await cache.get_or_set("key", factory) == "value-1"
    assert await cache.get_or_set("key", factory) == "value-2"
    assert calls == 2
