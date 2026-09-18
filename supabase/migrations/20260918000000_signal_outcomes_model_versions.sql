create table if not exists public.signal_outcomes (
    id uuid primary key default gen_random_uuid(),
    signal_id uuid not null,
    user_id uuid not null references auth.users(id) on delete cascade,
    symbol text not null,
    timeframe text not null check (timeframe in ('1h','4h','1day','1week')),
    signal_time timestamptz not null,
    outcome_time timestamptz,
    score integer not null check (score between -100 and 100),
    bias text not null,
    regime text not null,
    factor_scores jsonb not null default '{}'::jsonb,
    factor_contributions jsonb not null default '{}'::jsonb,
    outcome_return_pct numeric,
    outcome_label text,
    horizon_bars integer not null check (horizon_bars > 0),
    created_at timestamptz not null default timezone('utc', now()),
    unique(user_id, signal_id)
);
create index if not exists signal_outcomes_user_time_idx on public.signal_outcomes(user_id, signal_time desc);
create index if not exists signal_outcomes_model_idx on public.signal_outcomes(timeframe, regime, signal_time desc);
alter table public.signal_outcomes enable row level security;
drop policy if exists signal_outcomes_select_own on public.signal_outcomes;
create policy signal_outcomes_select_own on public.signal_outcomes for select to authenticated using ((select auth.uid()) = user_id);
drop policy if exists signal_outcomes_insert_own on public.signal_outcomes;
create policy signal_outcomes_insert_own on public.signal_outcomes for insert to authenticated with check ((select auth.uid()) = user_id);
drop policy if exists signal_outcomes_update_own on public.signal_outcomes;
create policy signal_outcomes_update_own on public.signal_outcomes for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
drop policy if exists signal_outcomes_delete_own on public.signal_outcomes;
create policy signal_outcomes_delete_own on public.signal_outcomes for delete to authenticated using ((select auth.uid()) = user_id);

create table if not exists public.model_versions (
    id uuid primary key default gen_random_uuid(),
    model_family text not null,
    version_id text not null unique,
    status text not null check (status in ('DRAFT','VALIDATED','ACTIVE','ROLLED_BACK')),
    weights jsonb not null,
    parent_version_id text,
    training_observations integer not null default 0 check (training_observations >= 0),
    oos_observations integer not null default 0 check (oos_observations >= 0),
    validation_metrics jsonb not null default '{}'::jsonb,
    artifact_checksum text not null,
    created_at timestamptz not null default timezone('utc', now()),
    activated_at timestamptz,
    rolled_back_at timestamptz
);
create unique index if not exists model_versions_active_family_idx on public.model_versions(model_family) where status = 'ACTIVE';
alter table public.model_versions enable row level security;
grant select, insert, update, delete on public.signal_outcomes to authenticated;
revoke all on public.model_versions from anon, authenticated;
