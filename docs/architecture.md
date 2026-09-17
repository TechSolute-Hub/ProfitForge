# Architecture

```text
Provider -> normalization/validation -> canonical snapshot
                                      -> validated OHLCV
                                      -> technical analysis
                                      -> structure/regime
                                      -> scoring/explainability
                                      -> research API -> frontend
```

## Data integrity
Market APIs are backend-only. Provider responses are parsed into canonical models and validated before being exposed. Current quotes carry source, timestamp and status. Provider failure produces `UNAVAILABLE` rather than a synthetic price.

## Phase 2 intelligence
The deterministic intelligence layer combines trend, momentum, market structure, volatility, explainable factor scoring and multi-timeframe confluence. Missing news/sentiment data is explicitly marked unavailable rather than fabricated.

## Phase 3 data reliability
The market service now caches validated quotes and OHLCV using a bounded process-local async TTL cache. Per-key locking prevents concurrent requests for the same uncached dataset from creating duplicate provider calls. Multi-timeframe history requests execute concurrently, while provider error details remain server-side.

The cache is intentionally process-local. It reduces duplicate requests and free-tier rate pressure but is not a durable shared cache; distributed caching and persistence belong to a later infrastructure phase.

## Production direction
Add provider fallbacks, durable database persistence, Supabase RLS-backed user/watchlist data, scheduled jobs, news/economic calendar ingestion, signal outcome tracking, backtesting with costs/slippage, adaptive weight versioning, observability and alert delivery.
