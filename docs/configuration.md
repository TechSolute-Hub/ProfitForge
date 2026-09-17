# Configuration

Set backend variables in `backend/.env` using `backend/.env.example` as the template.

## Market data

- `TWELVE_DATA_API_KEY`: primary server-side Twelve Data credential.
- `TWELVE_DATA_BASE_URL`: Twelve Data API base URL.
- `ALPHA_VANTAGE_API_KEY`: optional historical-data fallback credential.
- `ALPHA_VANTAGE_BASE_URL`: Alpha Vantage API endpoint.
- `PROVIDER_REQUEST_TIMEOUT_SECONDS`: timeout applied to external market-provider requests.
- `QUOTE_CACHE_SECONDS`: process-local TTL for validated current quotes; `0` disables quote caching.
- `BARS_CACHE_SECONDS`: process-local TTL for validated OHLCV history; `0` disables history caching.
- `MAX_DATA_AGE_SECONDS`: maximum accepted age before a quote becomes `STALE`.

Twelve Data remains the primary provider. Alpha Vantage is optional. The provider router may use it for supported OHLCV intervals when Twelve Data fails. Alpha Vantage stock quotes without realtime entitlement are treated as stale and are not allowed to masquerade as current prices.

## Supabase

- `SUPABASE_URL`: Supabase project URL.
- `SUPABASE_PUBLISHABLE_KEY`: browser-safe publishable key; never put a service-role key in frontend or user-state requests.
- `SUPABASE_REQUEST_TIMEOUT_SECONDS`: backend timeout for authenticated Supabase requests.

The frontend uses:

- `VITE_API_URL`: backend API origin.
- `VITE_SUPABASE_URL`: Supabase project URL.
- `VITE_SUPABASE_PUBLISHABLE_KEY`: browser-safe Supabase publishable key.

Provider secrets must never be exposed through Vite environment variables. The publishable Supabase key is designed for client use and is still constrained by grants and RLS.
