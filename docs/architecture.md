# Architecture

```text
Provider -> normalization/validation -> canonical snapshot
                                      -> technical analysis
                                      -> structure/regime
                                      -> scoring/explainability
                                      -> research API -> frontend
```

## Data integrity
Market APIs are backend-only. A provider response is parsed into canonical models and validated before being exposed. Current quotes carry source, timestamp and status. Provider failure produces `UNAVAILABLE` rather than a synthetic price.

## Intelligence
The first implementation is deterministic and inspectable. It combines trend, momentum, market structure and volatility. Adaptive weighting, news/sentiment, multi-timeframe confluence, persistence and LLM synthesis are intended as subsequent layers; they must not bypass data-quality validation.

## Production direction
Add provider fallbacks, cache/database persistence, Supabase RLS-backed user/watchlist data, scheduled jobs, news/economic calendar ingestion, signal outcome tracking, backtesting with costs/slippage, adaptive weight versioning, observability and alert delivery.
