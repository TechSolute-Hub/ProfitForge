# Supabase database foundation

Phase 4 introduces durable user-owned research state without coupling the market-intelligence engine to Supabase.

## Schema

The initial schema is in `supabase/migrations/20260917000000_initial_research_state.sql` and defines:

- `profiles` — optional application-level user profile data keyed to `auth.users`.
- `watchlists` — user-owned named watchlists.
- `watchlist_items` — symbols and asset classes inside a watchlist.
- `research_history` — immutable research observations with the structured analysis stored as `jsonb`.
- `saved_analyses` — user-named research snapshots that can be revisited later.

Signal/outcome tracking is deliberately not mixed into this first persistence migration. It will be added once the signal model and outcome-labeling rules are finalized, avoiding an unstable schema.

## Security model

All five tables have Row Level Security enabled. Data API access is granted to `authenticated` and `service_role`; `anon` is intentionally not granted table access. Policies restrict user-owned rows with `auth.uid()`.

Do not use `raw_user_meta_data` or editable user metadata for authorization. Ownership comes from the authenticated user's UUID and database relationships.

## Applying the schema

The SQL file is version-controlled as the Phase 4 schema artifact. Before applying it to a Supabase project:

1. Run the project migration through the Supabase CLI or SQL migration workflow.
2. Run the project's database security/advisor checks.
3. Execute positive and negative RLS tests for anonymous and authenticated users.
4. Verify that an authenticated user cannot read, insert, update, or delete another user's rows.
5. Verify that `service_role` remains server-side only.

The current GitHub integration does not expose a connected Supabase project ID, so this repository change does **not** claim that the production database has already been migrated.

## Application architecture

The backend uses `ResearchRepository` as the persistence boundary. The analysis engine remains independent of Supabase, so a later implementation can use Supabase, PostgreSQL, or a test double without changing technical-analysis code.
