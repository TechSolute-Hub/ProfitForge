-- ProfitForge Phase 4: durable user research state.
--
-- This migration is intentionally limited to user-owned application data.
-- Supabase Auth remains the source of identity via auth.users.
-- No market-data provider credentials or service-role secrets are stored here.

create extension if not exists pgcrypto;

create table if not exists public.profiles (
    user_id uuid primary key references auth.users(id) on delete cascade,
    display_name text,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.watchlists (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    name text not null,
    created_at timestamptz not null default timezone('utc', now()),
    updated_at timestamptz not null default timezone('utc', now()),
    constraint watchlists_name_not_blank check (length(trim(name)) > 0),
    constraint watchlists_user_name_unique unique (user_id, name)
);

create table if not exists public.watchlist_items (
    id uuid primary key default gen_random_uuid(),
    watchlist_id uuid not null references public.watchlists(id) on delete cascade,
    symbol text not null,
    asset_class text not null check (asset_class in ('stock', 'forex', 'crypto')),
    notes text,
    created_at timestamptz not null default timezone('utc', now()),
    constraint watchlist_items_symbol_not_blank check (length(trim(symbol)) > 0),
    constraint watchlist_items_unique unique (watchlist_id, symbol, asset_class)
);

create table if not exists public.research_history (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    symbol text not null,
    asset_class text not null check (asset_class in ('stock', 'forex', 'crypto')),
    timeframe text not null check (timeframe in ('1h', '4h', '1day', '1week')),
    observed_at timestamptz not null,
    score integer not null check (score between -100 and 100),
    confidence integer not null check (confidence between 0 and 100),
    bias text not null,
    regime text not null,
    result jsonb not null,
    created_at timestamptz not null default timezone('utc', now())
);

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

create index if not exists watchlists_user_id_idx
    on public.watchlists (user_id);

create index if not exists watchlist_items_watchlist_id_idx
    on public.watchlist_items (watchlist_id);

create index if not exists research_history_user_observed_idx
    on public.research_history (user_id, observed_at desc);

create index if not exists research_history_symbol_timeframe_idx
    on public.research_history (symbol, asset_class, timeframe, observed_at desc);

create index if not exists saved_analyses_user_updated_idx
    on public.saved_analyses (user_id, updated_at desc);

-- Expose only authenticated user-owned data through the Data API.
-- service_role retains server-side access, while anon receives no grants.
grant select, insert, update, delete on table
    public.profiles,
    public.watchlists,
    public.watchlist_items,
    public.research_history,
    public.saved_analyses
    to authenticated;

grant all on table
    public.profiles,
    public.watchlists,
    public.watchlist_items,
    public.research_history,
    public.saved_analyses
    to service_role;

alter table public.profiles enable row level security;
alter table public.watchlists enable row level security;
alter table public.watchlist_items enable row level security;
alter table public.research_history enable row level security;
alter table public.saved_analyses enable row level security;

create policy "users can read own profile"
on public.profiles
for select
to authenticated
using ((select auth.uid()) = user_id);

create policy "users can insert own profile"
on public.profiles
for insert
to authenticated
with check ((select auth.uid()) = user_id);

create policy "users can update own profile"
on public.profiles
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy "users can read own watchlists"
on public.watchlists
for select
to authenticated
using ((select auth.uid()) = user_id);

create policy "users can create own watchlists"
on public.watchlists
for insert
to authenticated
with check ((select auth.uid()) = user_id);

create policy "users can update own watchlists"
on public.watchlists
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy "users can delete own watchlists"
on public.watchlists
for delete
to authenticated
using ((select auth.uid()) = user_id);

create policy "users can read own watchlist items"
on public.watchlist_items
for select
to authenticated
using (
    exists (
        select 1
        from public.watchlists w
        where w.id = watchlist_id
          and w.user_id = (select auth.uid())
    )
);

create policy "users can create items in own watchlists"
on public.watchlist_items
for insert
to authenticated
with check (
    exists (
        select 1
        from public.watchlists w
        where w.id = watchlist_id
          and w.user_id = (select auth.uid())
    )
);

create policy "users can update items in own watchlists"
on public.watchlist_items
for update
to authenticated
using (
    exists (
        select 1
        from public.watchlists w
        where w.id = watchlist_id
          and w.user_id = (select auth.uid())
    )
)
with check (
    exists (
        select 1
        from public.watchlists w
        where w.id = watchlist_id
          and w.user_id = (select auth.uid())
    )
);

create policy "users can delete items in own watchlists"
on public.watchlist_items
for delete
to authenticated
using (
    exists (
        select 1
        from public.watchlists w
        where w.id = watchlist_id
          and w.user_id = (select auth.uid())
    )
);

create policy "users can read own research history"
on public.research_history
for select
to authenticated
using ((select auth.uid()) = user_id);

create policy "users can create own research history"
on public.research_history
for insert
to authenticated
with check ((select auth.uid()) = user_id);

create policy "users can delete own research history"
on public.research_history
for delete
to authenticated
using ((select auth.uid()) = user_id);

create policy "users can read own saved analyses"
on public.saved_analyses
for select
to authenticated
using ((select auth.uid()) = user_id);

create policy "users can create own saved analyses"
on public.saved_analyses
for insert
to authenticated
with check ((select auth.uid()) = user_id);

create policy "users can update own saved analyses"
on public.saved_analyses
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy "users can delete own saved analyses"
on public.saved_analyses
for delete
to authenticated
using ((select auth.uid()) = user_id);
