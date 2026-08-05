-- The Compute Record · M2.1 measurement and market semantics
-- Additive extension of 20260714180000_compute_domain.sql.

begin;

set local lock_timeout = '10s';
set local statement_timeout = '180s';
select pg_advisory_xact_lock(
  hashtextextended('computerecord:database-migrations', 0)
);

set local search_path = public, extensions, core, compute;

-- Canonical geography and infrastructure identities remain in the shared
-- entity graph. Enum additions are not consumed until after this transaction.
alter type core.entity_type add value if not exists 'market';
alter type core.entity_type add value if not exists 'infrastructure_node';

alter type compute.relationship_type add value if not exists 'depends_on';
alter type compute.relationship_type add value if not exists 'connected_to';
alter type compute.relationship_type add value if not exists 'located_in_market';
alter type compute.relationship_type add value if not exists 'supplies_power';
alter type compute.relationship_type add value if not exists 'supplies_water';
alter type compute.relationship_type add value if not exists 'supplies_fuel';
alter type compute.relationship_type add value if not exists 'supplies_fiber';

create type core.epistemic_type as enum (
  'observed',
  'administrative',
  'reported',
  'estimated',
  'modeled',
  'forecast',
  'derived'
);

create type compute.market_type as enum (
  'global', 'region', 'country', 'state', 'metro', 'submarket', 'corridor'
);

create type compute.infrastructure_node_type as enum (
  'utility_territory',
  'grid_supply_point',
  'substation',
  'transmission_line',
  'generation_asset',
  'fuel_supply',
  'water_supply',
  'fiber_route',
  'cable_landing',
  'other'
);

create type compute.metric_geography_type as enum (
  'global',
  'region',
  'country',
  'state',
  'metro',
  'submarket',
  'corridor',
  'campus',
  'phase',
  'building',
  'infrastructure_node'
);

create type compute.evidence_redistribution_status as enum (
  'unknown', 'private_only', 'derived_only', 'public_allowed'
);

create table compute.scenario (
  id uuid primary key default gen_random_uuid(),
  scenario_key text not null check (scenario_key ~ '^[a-z0-9]+([_-][a-z0-9]+)*$'),
  version integer not null check (version > 0),
  name text not null check (nullif(btrim(name), '') is not null),
  description text not null check (nullif(btrim(description), '') is not null),
  issued_at timestamptz not null,
  review_id uuid not null references public.review(id) on delete restrict,
  created_at timestamptz not null default now(),
  unique (scenario_key, version)
);
create index scenario_review_idx on compute.scenario (review_id);

alter table core.fact_version
  add column epistemic_type core.epistemic_type not null default 'reported',
  add column period_start date,
  add column period_end date,
  add column issued_at timestamptz,
  add column forecast_horizon date,
  add column scenario_id uuid references compute.scenario(id) on delete restrict,
  add constraint fact_period_shape check (
    period_end is null
    or (period_start is not null and period_end >= period_start)
  ),
  add constraint fact_forecast_shape check (
    (
      epistemic_type = 'forecast'
      and issued_at is not null
      and forecast_horizon is not null
      and forecast_horizon >= issued_at::date
    )
    or
    (
      epistemic_type <> 'forecast'
      and forecast_horizon is null
      and scenario_id is null
    )
  );

create index fact_subject_epistemic_state_idx
  on core.fact_version
  (subject_entity_id, epistemic_type, publication_state);
create index fact_scenario_idx on core.fact_version (scenario_id)
  where scenario_id is not null;
create index fact_period_idx on core.fact_version (period_start, period_end)
  where period_start is not null;

create table compute.market (
  entity_id uuid primary key references core.entity(id) on delete restrict,
  place_id uuid not null references compute.place(entity_id) on delete restrict,
  parent_market_id uuid references compute.market(entity_id) on delete restrict,
  market_type compute.market_type not null,
  methodology_version text not null
    check (nullif(btrim(methodology_version), '') is not null),
  constraint market_not_own_parent check (
    parent_market_id is null or parent_market_id <> entity_id
  )
);
create index market_place_idx on compute.market (place_id);
create index market_parent_idx on compute.market (parent_market_id)
  where parent_market_id is not null;
create index market_type_idx on compute.market (market_type);

create table compute.infrastructure_node (
  entity_id uuid primary key references core.entity(id) on delete restrict,
  place_id uuid not null references compute.place(entity_id) on delete restrict,
  operator_entity_id uuid references compute.organization(entity_id)
    on delete restrict,
  node_type compute.infrastructure_node_type not null,
  stable_identifier text,
  constraint infrastructure_identifier_nonempty check (
    stable_identifier is null or nullif(btrim(stable_identifier), '') is not null
  )
);
create index infrastructure_place_type_idx
  on compute.infrastructure_node (place_id, node_type);
create index infrastructure_operator_idx
  on compute.infrastructure_node (operator_entity_id)
  where operator_entity_id is not null;

create table compute.satellite_observation (
  fact_id uuid primary key references compute.observation_fact(fact_id)
    on delete restrict,
  provider text not null check (nullif(btrim(provider), '') is not null),
  scene_identifier text not null
    check (nullif(btrim(scene_identifier), '') is not null),
  acquired_at timestamptz not null,
  resolution_m numeric not null check (resolution_m > 0),
  cloud_cover_pct numeric check (
    cloud_cover_pct is null
    or (cloud_cover_pct >= 0 and cloud_cover_pct <= 100)
  ),
  license_code text not null check (nullif(btrim(license_code), '') is not null),
  redistribution_status compute.evidence_redistribution_status not null,
  scene_geometry geometry(Geometry, 4326),
  constraint satellite_geometry_valid check (
    scene_geometry is null or st_isvalid(scene_geometry)
  ),
  unique (provider, scene_identifier, acquired_at)
);
create index satellite_acquired_idx
  on compute.satellite_observation (acquired_at desc);
create index satellite_scene_geometry_idx
  on compute.satellite_observation using gist (scene_geometry);

create table compute.metric_definition (
  id uuid primary key default gen_random_uuid(),
  metric_key text not null check (metric_key ~ '^[a-z0-9]+([_.-][a-z0-9]+)*$'),
  version integer not null check (version > 0),
  name text not null check (nullif(btrim(name), '') is not null),
  description text not null check (nullif(btrim(description), '') is not null),
  unit text not null check (nullif(btrim(unit), '') is not null),
  geography_type compute.metric_geography_type not null,
  formula text not null check (nullif(btrim(formula), '') is not null),
  methodology text not null check (nullif(btrim(methodology), '') is not null),
  methodology_version text not null
    check (nullif(btrim(methodology_version), '') is not null),
  review_id uuid not null references public.review(id) on delete restrict,
  created_at timestamptz not null default now(),
  unique (metric_key, version)
);
create index metric_definition_review_idx
  on compute.metric_definition (review_id);

create table compute.metric_definition_fact_kind (
  metric_definition_id uuid not null references compute.metric_definition(id)
    on delete restrict,
  fact_kind core.fact_kind not null,
  primary key (metric_definition_id, fact_kind)
);

create table compute.metric_definition_epistemic_type (
  metric_definition_id uuid not null references compute.metric_definition(id)
    on delete restrict,
  epistemic_type core.epistemic_type not null,
  primary key (metric_definition_id, epistemic_type)
);

create table compute.metric_definition_capacity_type (
  metric_definition_id uuid not null references compute.metric_definition(id)
    on delete restrict,
  capacity_type text not null references compute.capacity_vocabulary(capacity_type)
    on delete restrict,
  primary key (metric_definition_id, capacity_type)
);
create index metric_definition_capacity_type_idx
  on compute.metric_definition_capacity_type (capacity_type);

create table compute.metric_observation (
  id uuid primary key default gen_random_uuid(),
  logical_id uuid not null default gen_random_uuid(),
  metric_definition_id uuid not null references compute.metric_definition(id)
    on delete restrict,
  subject_entity_id uuid not null references core.entity(id) on delete restrict,
  period_start date not null,
  period_end date not null,
  issued_at timestamptz not null,
  qualifier compute.quantity_qualifier not null,
  value numeric,
  lower_bound numeric,
  upper_bound numeric,
  coverage_numerator numeric,
  coverage_denominator numeric,
  uncertainty text,
  publication_state core.publication_state not null default 'candidate',
  review_id uuid references public.review(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint metric_period_shape check (period_end >= period_start),
  constraint metric_quantity_shape check (
    (
      qualifier = 'range'
      and value is null
      and lower_bound is not null
      and upper_bound is not null
      and lower_bound <= upper_bound
    )
    or
    (
      qualifier <> 'range'
      and value is not null
      and lower_bound is null
      and upper_bound is null
    )
  ),
  constraint metric_coverage_shape check (
    (coverage_numerator is null and coverage_denominator is null)
    or
    (
      coverage_numerator is not null
      and coverage_denominator is not null
      and coverage_numerator >= 0
      and coverage_denominator > 0
      and coverage_numerator <= coverage_denominator
    )
  ),
  constraint metric_published_has_review check (
    publication_state not in ('published', 'retracted') or review_id is not null
  ),
  unique (id, logical_id)
);
create unique index metric_one_published_period_idx
  on compute.metric_observation
  (metric_definition_id, subject_entity_id, period_start, period_end)
  where publication_state = 'published';
create unique index metric_one_staging_version_idx
  on compute.metric_observation (logical_id)
  where publication_state = 'staging';
create index metric_subject_period_idx
  on compute.metric_observation
  (subject_entity_id, metric_definition_id, period_end desc);
create index metric_review_idx on compute.metric_observation (review_id)
  where review_id is not null;

create table compute.metric_observation_input (
  metric_observation_id uuid not null references compute.metric_observation(id)
    on delete restrict,
  input_fact_id uuid not null references core.fact_version(id) on delete restrict,
  primary key (metric_observation_id, input_fact_id)
);
create index metric_observation_input_fact_idx
  on compute.metric_observation_input (input_fact_id);

create trigger market_entity_type
  before insert or update of entity_id on compute.market
  for each row execute function core.enforce_entity_type('market');
create trigger infrastructure_node_entity_type
  before insert or update of entity_id on compute.infrastructure_node
  for each row execute function core.enforce_entity_type('infrastructure_node');

create function compute.enforce_satellite_observation()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  observation_row compute.observation_fact%rowtype;
begin
  select * into observation_row
  from compute.observation_fact o
  where o.fact_id = new.fact_id;

  if observation_row.observation_type not in (
    'satellite_asset_count', 'construction_activity', 'equipment_presence'
  ) then
    raise exception 'satellite metadata requires a remote-observation fact'
      using errcode = '23514';
  end if;
  if observation_row.observed_at is distinct from new.acquired_at then
    raise exception 'satellite acquisition time must equal observation time'
      using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger satellite_observation_shape
  before insert or update on compute.satellite_observation
  for each row execute function compute.enforce_satellite_observation();

-- The new measurement fields are part of immutable fact semantics.
create or replace function core.preserve_fact_version_history()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'fact versions are append-only' using errcode = '23514';
  end if;

  if new.id is distinct from old.id
     or new.logical_id is distinct from old.logical_id
     or new.subject_entity_id is distinct from old.subject_entity_id
     or new.fact_kind is distinct from old.fact_kind
     or new.lineage_kind is distinct from old.lineage_kind
     or new.valid_from is distinct from old.valid_from
     or new.valid_to is distinct from old.valid_to
     or new.recorded_at is distinct from old.recorded_at
     or new.epistemic_type is distinct from old.epistemic_type
     or new.period_start is distinct from old.period_start
     or new.period_end is distinct from old.period_end
     or new.issued_at is distinct from old.issued_at
     or new.forecast_horizon is distinct from old.forecast_horizon
     or new.scenario_id is distinct from old.scenario_id
     or new.verification_state is distinct from old.verification_state
     or new.supersedes_fact_id is distinct from old.supersedes_fact_id
     or new.created_at is distinct from old.created_at then
    raise exception 'fact version semantics are immutable; create a correction version'
      using errcode = '23514';
  end if;

  if old.review_id is not null and new.review_id is distinct from old.review_id then
    raise exception 'a fact review binding is immutable' using errcode = '23514';
  end if;

  if not (
    (old.publication_state = 'candidate' and new.publication_state in ('candidate', 'staging'))
    or (old.publication_state = 'staging' and new.publication_state in ('staging', 'published'))
    or (old.publication_state = 'published' and new.publication_state = 'retracted')
    or (old.publication_state = 'retracted' and new.publication_state = 'retracted')
  ) then
    raise exception 'invalid fact publication transition % -> %',
      old.publication_state, new.publication_state using errcode = '23514';
  end if;

  if old.publication_state = 'retracted' then
    raise exception 'retracted fact versions are immutable' using errcode = '23514';
  end if;

  new.updated_at := now();
  return new;
end;
$$;

create function compute.preserve_metric_definition()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  raise exception 'metric definitions are immutable; create a new version'
    using errcode = '23514';
end;
$$;

create trigger preserve_metric_definition
  before update or delete on compute.metric_definition
  for each row execute function compute.preserve_metric_definition();

create function compute.preserve_metric_observation()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'metric observations are append-only' using errcode = '23514';
  end if;
  if new.id is distinct from old.id
     or new.logical_id is distinct from old.logical_id
     or new.metric_definition_id is distinct from old.metric_definition_id
     or new.subject_entity_id is distinct from old.subject_entity_id
     or new.period_start is distinct from old.period_start
     or new.period_end is distinct from old.period_end
     or new.issued_at is distinct from old.issued_at
     or new.qualifier is distinct from old.qualifier
     or new.value is distinct from old.value
     or new.lower_bound is distinct from old.lower_bound
     or new.upper_bound is distinct from old.upper_bound
     or new.coverage_numerator is distinct from old.coverage_numerator
     or new.coverage_denominator is distinct from old.coverage_denominator
     or new.uncertainty is distinct from old.uncertainty
     or new.created_at is distinct from old.created_at then
    raise exception 'metric observation semantics are immutable; create a correction'
      using errcode = '23514';
  end if;
  if old.review_id is not null and new.review_id is distinct from old.review_id then
    raise exception 'metric review binding is immutable' using errcode = '23514';
  end if;
  if not (
    (old.publication_state = 'candidate' and new.publication_state in ('candidate', 'staging'))
    or (old.publication_state = 'staging' and new.publication_state in ('staging', 'published'))
    or (old.publication_state = 'published' and new.publication_state = 'retracted')
    or (old.publication_state = 'retracted' and new.publication_state = 'retracted')
  ) then
    raise exception 'invalid metric publication transition % -> %',
      old.publication_state, new.publication_state using errcode = '23514';
  end if;
  if old.publication_state = 'retracted' then
    raise exception 'retracted metric observations are immutable'
      using errcode = '23514';
  end if;
  new.updated_at := now();
  return new;
end;
$$;

create trigger preserve_metric_observation
  before update or delete on compute.metric_observation
  for each row execute function compute.preserve_metric_observation();

create function compute.preserve_metric_input()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  target_observation_id uuid;
  target_state core.publication_state;
begin
  target_observation_id := case
    when tg_op = 'DELETE' then old.metric_observation_id
    else new.metric_observation_id
  end;
  select o.publication_state into target_state
  from compute.metric_observation o
  where o.id = target_observation_id;
  if target_state in ('published', 'retracted') then
    raise exception 'inputs for % metric observation % are immutable',
      target_state, target_observation_id using errcode = '23514';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end;
$$;

create trigger preserve_metric_input
  before insert or update or delete on compute.metric_observation_input
  for each row execute function compute.preserve_metric_input();

create function compute.assert_metric_observation_ready(p_observation_id uuid)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
  observation_row compute.metric_observation%rowtype;
begin
  select * into observation_row
  from compute.metric_observation o
  where o.id = p_observation_id;
  if not found or observation_row.publication_state <> 'published' then
    return;
  end if;

  if not exists (
    select 1
    from compute.metric_observation_input i
    join core.fact_version f on f.id = i.input_fact_id
    where i.metric_observation_id = observation_row.id
      and f.publication_state = 'published'
  ) then
    raise exception 'published metric observation % requires published input facts',
      observation_row.id using errcode = '23514';
  end if;

  if exists (
    select 1
    from compute.metric_observation_input i
    join core.fact_version f on f.id = i.input_fact_id
    where i.metric_observation_id = observation_row.id
      and (
        f.publication_state <> 'published'
        or not exists (
          select 1
          from compute.metric_definition_fact_kind allowed
          where allowed.metric_definition_id = observation_row.metric_definition_id
            and allowed.fact_kind = f.fact_kind
        )
        or not exists (
          select 1
          from compute.metric_definition_epistemic_type allowed
          where allowed.metric_definition_id = observation_row.metric_definition_id
            and allowed.epistemic_type = f.epistemic_type
        )
        or (
          f.fact_kind = 'capacity'
          and not exists (
            select 1
            from compute.capacity_fact capacity_row
            join compute.metric_definition_capacity_type allowed
              on allowed.capacity_type = capacity_row.capacity_type
            where capacity_row.fact_id = f.id
              and allowed.metric_definition_id = observation_row.metric_definition_id
          )
        )
      )
  ) then
    raise exception 'metric observation % has incompatible input facts',
      observation_row.id using errcode = '23514';
  end if;
end;
$$;

create function compute.enforce_metric_observation_ready_trigger()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  target_observation_id uuid;
begin
  if tg_table_name = 'metric_observation' then
    target_observation_id := case when tg_op = 'DELETE' then old.id else new.id end;
  else
    target_observation_id := case
      when tg_op = 'DELETE' then old.metric_observation_id
      else new.metric_observation_id
    end;
  end if;
  if target_observation_id is not null then
    perform compute.assert_metric_observation_ready(target_observation_id);
  end if;
  return null;
end;
$$;

create constraint trigger metric_observation_truth_guard
  after insert or update on compute.metric_observation
  deferrable initially deferred
  for each row execute function compute.enforce_metric_observation_ready_trigger();
create constraint trigger metric_observation_input_truth_guard
  after insert or update or delete on compute.metric_observation_input
  deferrable initially deferred
  for each row execute function compute.enforce_metric_observation_ready_trigger();

-- Append the epistemic fields without changing the existing view contract.
create or replace view core.fact_evidence
with (security_invoker = true)
as
select
  f.id as fact_id,
  f.logical_id,
  f.fact_kind,
  f.publication_state,
  s.id as support_id,
  s.support_kind,
  s.derivation,
  c.id as claim_id,
  c.document_id,
  d.url as source_url,
  d.sha256 as document_sha256,
  d.r2_key,
  c.quote,
  c.page,
  coalesce(
    array_agg(i.input_fact_id order by i.input_fact_id)
      filter (where i.input_fact_id is not null),
    '{}'::uuid[]
  ) as input_fact_ids,
  f.epistemic_type,
  f.period_start,
  f.period_end,
  f.issued_at,
  f.forecast_horizon,
  f.scenario_id
from core.fact_version f
join core.fact_support s on s.fact_id = f.id
left join public.claim c on c.id = s.claim_id
left join public.document d on d.id = c.document_id
left join core.fact_support_input i on i.support_id = s.id
group by f.id, f.logical_id, f.fact_kind, f.publication_state,
  s.id, s.support_kind, s.derivation, c.id, c.document_id,
  d.url, d.sha256, d.r2_key, c.quote, c.page,
  f.epistemic_type, f.period_start, f.period_end, f.issued_at,
  f.forecast_horizon, f.scenario_id;

create or replace view compute.current_capacity
with (security_invoker = true)
as
select
  f.id as fact_id,
  f.logical_id,
  f.subject_entity_id,
  f.verification_state,
  f.valid_from,
  f.valid_to,
  c.capacity_type,
  v.capacity_family,
  c.capacity_basis,
  c.qualifier,
  c.value_mw,
  c.lower_mw,
  c.upper_mw,
  c.scope_entity_id,
  f.epistemic_type,
  f.period_start,
  f.period_end,
  f.issued_at,
  f.forecast_horizon,
  f.scenario_id
from core.fact_version f
join compute.capacity_fact c on c.fact_id = f.id
join compute.capacity_vocabulary v on v.capacity_type = c.capacity_type
where f.publication_state = 'published';

create view compute.actual_capacity
with (security_invoker = true)
as
select *
from compute.current_capacity
where epistemic_type in ('observed', 'administrative', 'reported', 'derived');

create view compute.forecast_capacity
with (security_invoker = true)
as
select *
from compute.current_capacity
where epistemic_type = 'forecast';

create or replace function compute.sum_exact_capacity_mw(
  p_capacity_type text,
  p_scope_entity_id uuid
)
returns numeric
language plpgsql
stable
security invoker
set search_path = ''
as $$
declare
  result numeric;
begin
  if p_capacity_type is null or p_scope_entity_id is null then
    raise exception 'capacity_type and scope_entity_id are required'
      using errcode = '22004';
  end if;
  if not exists (
    select 1 from compute.capacity_vocabulary v
    where v.capacity_type = p_capacity_type
  ) then
    raise exception 'unknown capacity type %', p_capacity_type
      using errcode = '22023';
  end if;
  select sum(c.value_mw) into result
  from compute.actual_capacity c
  where c.capacity_type = p_capacity_type
    and c.scope_entity_id = p_scope_entity_id
    and c.qualifier = 'exact';
  return result;
end;
$$;

create view compute.current_metric_observation
with (security_invoker = true)
as
select
  o.id,
  o.logical_id,
  d.metric_key,
  d.version as metric_version,
  d.name,
  d.unit,
  d.geography_type,
  d.formula,
  d.methodology_version,
  o.subject_entity_id,
  o.period_start,
  o.period_end,
  o.issued_at,
  o.qualifier,
  o.value,
  o.lower_bound,
  o.upper_bound,
  o.coverage_numerator,
  o.coverage_denominator,
  o.uncertainty,
  coalesce(
    array_agg(i.input_fact_id order by i.input_fact_id)
      filter (where i.input_fact_id is not null),
    '{}'::uuid[]
  ) as input_fact_ids
from compute.metric_observation o
join compute.metric_definition d on d.id = o.metric_definition_id
left join compute.metric_observation_input i on i.metric_observation_id = o.id
where o.publication_state = 'published'
group by o.id, d.id;

-- Operational schemas are private. Public products consume snapshots only.
alter table compute.scenario enable row level security;
alter table compute.scenario force row level security;
alter table compute.market enable row level security;
alter table compute.market force row level security;
alter table compute.infrastructure_node enable row level security;
alter table compute.infrastructure_node force row level security;
alter table compute.satellite_observation enable row level security;
alter table compute.satellite_observation force row level security;
alter table compute.metric_definition enable row level security;
alter table compute.metric_definition force row level security;
alter table compute.metric_definition_fact_kind enable row level security;
alter table compute.metric_definition_fact_kind force row level security;
alter table compute.metric_definition_epistemic_type enable row level security;
alter table compute.metric_definition_epistemic_type force row level security;
alter table compute.metric_definition_capacity_type enable row level security;
alter table compute.metric_definition_capacity_type force row level security;
alter table compute.metric_observation enable row level security;
alter table compute.metric_observation force row level security;
alter table compute.metric_observation_input enable row level security;
alter table compute.metric_observation_input force row level security;

revoke all on all tables in schema core, compute
  from public, anon, authenticated;
revoke all on all sequences in schema core, compute
  from public, anon, authenticated;
revoke all on all functions in schema core, compute
  from public, anon, authenticated;

grant select, insert, update, delete on all tables in schema core, compute
  to service_role;
grant usage, select on all sequences in schema core, compute to service_role;
grant execute on all functions in schema core, compute to service_role;

comment on type core.epistemic_type is
  'How a fact value was produced; orthogonal to verification and publication state.';
comment on table compute.metric_definition is
  'Immutable, reviewed definitions for reproducible campus and market indicators.';
comment on table compute.metric_observation is
  'Versioned metric points with period, vintage, coverage, uncertainty, review, and exact fact inputs.';
comment on table compute.satellite_observation is
  'Licensed scene metadata attached only to observation facts; never a capacity payload.';
comment on view compute.actual_capacity is
  'Published capacity excluding estimated, modeled, and forecast epistemic types.';
comment on view compute.forecast_capacity is
  'Published capacity explicitly classified as forecast.';

commit;
