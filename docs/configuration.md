# Configuration

Set backend variables in `backend/.env` using `.env.example` as the template.

- `TWELVE_DATA_API_KEY`: server-side Twelve Data credential.
- `CORS_ORIGINS`: comma-separated frontend origins.
- `QUOTE_CACHE_SECONDS`: process-local TTL for validated current quotes; `0` disables quote caching.
- `BARS_CACHE_SECONDS`: process-local TTL for validated OHLCV history; `0` disables history caching.
- `MAX_DATA_AGE_SECONDS`: maximum accepted age before a quote becomes `STALE`.

Set `frontend/.env` with `VITE_API_URL` pointing to the backend. Provider secrets must never be exposed through Vite environment variables.
