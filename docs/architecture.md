# Architecture

```text
Market providers -> provider router -> normalization/validation -> canonical snapshot
                                         -> validated OHLCV
                                         -> technical analysis
                                         -> structure/regime
                                         -> scoring/explainability
                                         -> context: news/sentiment/economic events
                                         -> research API -> frontend
                                                        -> authenticated user state
                                                           -> Supabase/Postgres

Historical OHLCV + point-in-time scores
                  -> no-look-ahead backtest
                  -> costs/slippage
                  -> outcome labels
                  -> validation metrics
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

## Phase 6 contextual intelligence
News and sentiment are supplied by an optional Alpha Vantage context provider. The context layer preserves article timestamps, source URLs, relevance and sentiment metadata. Economic context currently includes supported stock earnings events. Context is cached independently from market prices and is retrieved concurrently with other research inputs.

The `news_sentiment` scoring factor is only enabled when real provider data is available. Missing or failed context is excluded and the remaining factor weights are renormalized; no synthetic neutral sentiment is inserted.

## Phase 7 validation and backtesting
The backtest engine is deliberately separate from live research analysis. A score at bar `t` is treated as available only after bar `t` closes; an entry therefore occurs at bar `t+1` open. The engine supports explicit fees and slippage, configurable stop-loss/take-profit assumptions, bounded holding periods, chronological-data validation and conservative handling when both stop and target are touched within one candle.

Forward outcome labeling likewise uses the next bar's open and later bars only. Insufficient future data produces an unresolved label instead of a fabricated outcome. These contracts are intended to prevent look-ahead leakage when historical signals are later connected to adaptive learning or model validation.

## Production direction
Next phases should add rolling/out-of-sample validation, walk-forward evaluation, signal/outcome persistence, adaptive weight versioning, observability, scheduled research jobs, alert delivery and additional provider coverage where freshness and licensing requirements are satisfied.

## Phase 7.2 walk-forward and out-of-sample validation
Rolling validation windows keep training observations strictly before test observations. An optional purge gap separates the two segments to reduce label overlap. The validation layer reports train and OOS trade count, win rate, return, drawdown, profit factor and expectancy, while marking insufficient samples explicitly. It does not fit or tune a model on the OOS segment.

Scores supplied to validation are point-in-time observations. Future work that generates scores from learned parameters must fit those parameters inside each training window and then freeze them before evaluating the corresponding OOS window.

## Phase 8 adaptive learning and model version management
The adaptive learner proposes changes only to research-factor weights from validated observations. Each factor requires a minimum sample size; weights are bounded and normalized after updates. The learner has no interface for risk limits, position sizing, execution controls or safety thresholds.

Candidate model versions are immutable records with parent lineage, training/OOS observation counts, validation metrics and an artifact checksum. A version must first be marked VALIDATED and can then be explicitly activated. Promotion policy and activation are separate so validation does not silently become deployment. Activating a new version rolls the prior active version back to a retained version record.

Machine-learning promotion remains a later controlled step: candidate models must be evaluated OOS and explicitly promoted after validation. Adaptive learning cannot automatically increase risk.
