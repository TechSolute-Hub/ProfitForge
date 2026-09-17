-- ProfitForge Phase 4.1: align the deployed research schema with the
-- repository contract used by the authenticated user-state API.
--
-- The connected Supabase project already contains watchlists and research_history
-- tables. This migration adds only the missing fields/table; it does not replace
-- the existing research schema.

alter table public.watchlist_items
    add column if not exists asset_class text not null default 'stock';

alter table public.watchlist_items
    add column if not exists notes text;

alter table public.watchlist_items
    drop constraint if exists watchlist_items_unique;

alter table public.watchlist_items
    add constraint watchlist_items_unique
    unique (watchlist_id, symbol, asset_class);

alter table public.watchlist_items
    drop constraint if exists watchlist_items_asset_class_check;

alter table public.watchlist_items
    add constraint watchlist_items_asset_class_check
    check (asset_class in ('stock', 'forex', 'crypto'));

alter table public.watchlist_items
    alter column asset_class drop default;

create table if not exists public.saved_analyses (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    name text not null,
    symbol text not null,
    asset_class text not null check (asset_class in ('stock', 'forex', 'crypto')),
    timeframe text not null check (timeframe in ('1h', '4h', '1day', '1week')),
    result jsonb not null,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint saved_analyses_name_not_blank check (length(trim(name)) > 0)
);

create index if not exists saved_analyses_user_updated_idx
    on public.saved_analyses (user_id, updated_at desc);

grant select, insert, update, delete on public.saved_analyses to authenticated;
grant all on public.saved_analyses to service_role;

alter table public.saved_analyses enable row level security;

drop policy if exists saved_analyses_select_own on public.saved_analyses;
drop policy if exists saved_analyses_insert_own on public.saved_analyses;
drop policy if exists saved_analyses_update_own on public.saved_analyses;
drop policy if exists saved_analyses_delete_own on public.saved_analyses;

create policy saved_analyses_select_own on public.saved_analyses
for select to authenticated
using ((select auth.uid()) = user_id);

create policy saved_analyses_insert_own on public.saved_analyses
for insert to authenticated
with check ((select auth.uid()) = user_id);

create policy saved_analyses_update_own on public.saved_analyses
for update to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy saved_analyses_delete_own on public.saved_analyses
for delete to authenticated
using ((select auth.uid()) = user_id);
