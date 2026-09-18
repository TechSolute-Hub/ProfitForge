create table if not exists public.signal_outcomes (
    id uuid primary key default gen_random_uuid(),
    signal_id uuid not null,
    user_id uuid not null references auth.users(id) on delete cascade,
    symbol text not null,
    asset_class text not null check (asset_class in ('stock','forex','crypto')),
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
    verified boolean not null default false,
    verified_at timestamptz,
    created_at timestamptz not null default timezone('utc', now()),
    unique(user_id, signal_id)
);

alter table public.signal_outcomes
    add column if not exists asset_class text;
alter table public.signal_outcomes
    add column if not exists verified boolean not null default false;
alter table public.signal_outcomes
    add column if not exists verified_at timestamptz;
do $
begin
    if not exists (
        select 1 from pg_constraint
        where conname = 'signal_outcomes_asset_class_check'
    ) then
        alter table public.signal_outcomes
            add constraint signal_outcomes_asset_class_check
            check (asset_class in ('stock', 'forex', 'crypto'));
    end if;
end $;

create index if not exists signal_outcomes_user_time_idx
    on public.signal_outcomes(user_id, signal_time desc);
create index if not exists signal_outcomes_model_idx
    on public.signal_outcomes(timeframe, regime, signal_time desc);
create index if not exists signal_outcomes_verified_idx
    on public.signal_outcomes(verified, signal_time asc);

alter table public.signal_outcomes enable row level security;

drop policy if exists signal_outcomes_select_own on public.signal_outcomes;
create policy signal_outcomes_select_own
    on public.signal_outcomes for select to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists signal_outcomes_insert_own on public.signal_outcomes;
create policy signal_outcomes_insert_own
    on public.signal_outcomes for insert to authenticated
    with check (
        (select auth.uid()) = user_id
        and verified = false
    );

drop policy if exists signal_outcomes_update_own on public.signal_outcomes;
create policy signal_outcomes_update_own
    on public.signal_outcomes for update to authenticated
    using ((select auth.uid()) = user_id)
    with check (
        (select auth.uid()) = user_id
        and verified = false
    );

drop policy if exists signal_outcomes_delete_own on public.signal_outcomes;
create policy signal_outcomes_delete_own
    on public.signal_outcomes for delete to authenticated
    using ((select auth.uid()) = user_id);

grant select, insert, update, delete on public.signal_outcomes to authenticated;
grant select, insert, update, delete on public.signal_outcomes to service_role;

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

create unique index if not exists model_versions_active_family_idx
    on public.model_versions(model_family) where status = 'ACTIVE';

alter table public.model_versions enable row level security;
revoke all on public.model_versions from anon, authenticated;
grant select, insert, update, delete on public.model_versions to service_role;

create or replace function public.activate_model_version(p_version_id text)
returns public.model_versions
language plpgsql
security invoker
set search_path = ''
as $$
declare
    target public.model_versions;
    current_version public.model_versions;
begin
    select *
    into target
    from public.model_versions
    where version_id = p_version_id
      and status = 'VALIDATED'
    for update;

    if not found then
        raise exception 'Only a VALIDATED model version can be activated';
    end if;

    select *
    into current_version
    from public.model_versions
    where model_family = target.model_family
      and status = 'ACTIVE'
    for update;

    if found then
        update public.model_versions
        set status = 'ROLLED_BACK',
            rolled_back_at = timezone('utc', now())
        where id = current_version.id;
    end if;

    update public.model_versions
    set status = 'ACTIVE',
        activated_at = timezone('utc', now())
    where id = target.id
    returning * into target;

    return target;
end;
$$;

revoke execute on function public.activate_model_version(text) from public, anon, authenticated;
grant execute on function public.activate_model_version(text) to service_role;
