# Architecture

```text
Market providers -> provider router -> normalization/validation -> canonical snapshot
                                         -> validated OHLCV
                                         -> technical analysis
                                         -> structure/regime
                                         -> scoring/explainability
                                         -> research API -> frontend
                                                        -> authenticated user state
                                                           -> Supabase/Postgres
```

## Data integrity
Market APIs are backend-only. Provider responses are parsed into canonical models and validated before being exposed. Current quotes carry source, timestamp and status. Provider failure produces `UNAVAILABLE` rather than a synthetic price.

## Phase 2 intelligence
The deterministic intelligence layer combines trend, momentum, market structure, volatility, explainable factor scoring and multi-timeframe confluence. Missing news/sentiment data is explicitly marked unavailable rather than fabricated.

## Phase 3 data reliability
The market service caches validated quotes and OHLCV using a bounded process-local async TTL cache. Per-key locking prevents concurrent requests for the same uncached dataset from creating duplicate provider calls. Multi-timeframe history requests execute concurrently, while provider error details remain server-side.

The service is process-shared through a cached dependency, so the process-local cache survives across HTTP requests. The cache is still not a distributed cache and is reset when a process restarts or a new deployment is created.

## Phase 4 durable user state
User-owned persistence is isolated behind `ResearchRepository`; the technical-analysis engine does not depend on Supabase APIs. The authenticated frontend uses Supabase Auth, while the backend validates the user's bearer token before accessing user state. The Supabase foundation provides RLS-protected tables for profiles, watchlists, watchlist items, research history and saved analyses.

The Data API access model is least-privilege: authenticated users receive table access subject to ownership policies, anonymous users receive no application-table access, and `service_role` remains server-side. The schema is version-controlled under `supabase/migrations/`.

## Phase 5 provider resilience
The market service now uses a deterministic provider router. Twelve Data remains the primary provider. Alpha Vantage is an optional fallback configured through `ALPHA_VANTAGE_API_KEY`. Historical OHLCV requests may fall back when the primary provider fails. A fallback stock quote that Alpha Vantage reports without realtime entitlement is marked `STALE` and is rejected from the current-price research path rather than being presented as live.

Provider failures are isolated at the provider boundary. The analysis layer receives only canonical `MarketSnapshot` and `OHLCVBar` models, so adding another provider does not require changes to technical-analysis code.

## Production direction
Next phases should add news/economic-calendar ingestion, scheduled research jobs, signal outcome tracking, backtesting with costs/slippage, adaptive weight versioning, observability, alert delivery, and additional provider coverage where freshness and licensing requirements are satisfied.
