# Architecture

```text
Provider -> normalization/validation -> canonical snapshot
                                      -> validated OHLCV
                                      -> technical analysis
                                      -> structure/regime
                                      -> scoring/explainability
                                      -> research API -> frontend
                                                     -> persistence boundary
                                                        -> Supabase/Postgres
```

## Data integrity
Market APIs are backend-only. Provider responses are parsed into canonical models and validated before being exposed. Current quotes carry source, timestamp and status. Provider failure produces `UNAVAILABLE` rather than a synthetic price.

## Phase 2 intelligence
The deterministic intelligence layer combines trend, momentum, market structure, volatility, explainable factor scoring and multi-timeframe confluence. Missing news/sentiment data is explicitly marked unavailable rather than fabricated.

## Phase 3 data reliability
The market service caches validated quotes and OHLCV using a bounded process-local async TTL cache. Per-key locking prevents concurrent requests for the same uncached dataset from creating duplicate provider calls. Multi-timeframe history requests execute concurrently, while provider error details remain server-side.

The service is now process-shared through a cached dependency, so the process-local cache survives across HTTP requests. The cache is still not a distributed cache and is reset when a process restarts or a new deployment is created.

## Phase 4 durable user state
User-owned persistence is isolated behind `ResearchRepository`; the technical-analysis engine does not depend on Supabase APIs. The Supabase foundation provides RLS-protected tables for profiles, watchlists, watchlist items, research history and saved analyses.

The Data API access model is least-privilege: authenticated users receive table access subject to ownership policies, anonymous users receive no application-table access, and `service_role` remains server-side. The schema is version-controlled under `supabase/migrations/`.

Signal/outcome persistence is intentionally deferred until the signal model and outcome-labeling contract are finalized. This prevents the database schema from encoding provisional trading semantics.

## Production direction
Next phases should add an actual Supabase repository implementation and authenticated frontend state, provider fallbacks, scheduled jobs, news/economic calendar ingestion, signal outcome tracking, backtesting with costs/slippage, adaptive weight versioning, observability and alert delivery.
