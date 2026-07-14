-- The Compute Record · M2 compute domain
-- Depends on the BTW shared-truth baseline through public.claim and
-- public.review.  This migration is additive: it does not alter BTW tables.

begin;

create schema if not exists extensions;
create extension if not exists postgis with schema extensions;
create schema if not exists core;
create schema if not exists compute;

set local search_path = public, extensions, core, compute;

create type core.entity_type as enum (
  'organization',
  'place',
  'campus',
  'campus_phase',
  'building',
  'power_asset',
  'equipment_cohort'
);
create type core.fact_kind as enum (
  'capacity', 'status', 'relationship', 'milestone', 'equipment', 'observation'
);
create type core.verification_state as enum (
  'source_asserted', 'corroborated', 'verified', 'disputed'
);
create type core.publication_state as enum (
  'candidate', 'staging', 'published', 'retracted'
);
create type core.lineage_kind as enum ('direct', 'derived');
create type core.support_kind as enum ('direct', 'derived');
create type core.alias_kind as enum (
  'legal', 'trade', 'former', 'project', 'source_label', 'other'
);

create type compute.organization_type as enum (
  'operator', 'developer', 'tenant', 'utility', 'vendor', 'investor',
  'government', 'regulator', 'other'
);
create type compute.geo_precision as enum (
  'country', 'state', 'county', 'city', 'parcel', 'building', 'exact'
);
create type compute.capacity_family as enum (
  'utility_service', 'generation', 'it'
);
create type compute.capacity_basis as enum (
  'service_limit', 'gross_nameplate', 'permitted', 'critical_it',
  'contracted_it', 'energized_it', 'occupied_it', 'planned_it'
);
create type compute.quantity_qualifier as enum (
  'exact', 'approximate', 'at_least', 'at_most', 'range'
);
create type compute.status_axis as enum (
  'site_control', 'zoning', 'environmental', 'utility', 'construction',
  'compute', 'commercial', 'finance'
);
create type compute.relationship_type as enum (
  'owns', 'develops', 'operates', 'leases_to', 'tenant_of',
  'utility_serves', 'supplies', 'finances', 'parent_of', 'subsidiary_of',
  'part_of'
);
create type compute.date_precision as enum ('day', 'month', 'quarter', 'year');
create type compute.milestone_type as enum (
  'announced', 'site_acquired', 'permit_filed', 'permit_issued',
  'construction_started', 'energized', 'commissioned', 'compute_started'
);
create type compute.power_asset_type as enum (
  'utility_service', 'substation', 'transmission', 'behind_meter_generation',
  'battery_storage', 'other'
);
create type compute.equipment_basis as enum (
  'announced', 'contracted', 'permitted', 'reported', 'observed', 'installed'
);
create type compute.observation_type as enum (
  'satellite_asset_count', 'construction_activity', 'utility_energization',
  'gas_flow', 'thermal_activity', 'equipment_presence', 'other'
);

create table core.entity (
  id uuid primary key default gen_random_uuid(),
  entity_type core.entity_type not null,
  canonical_name text not null check (nullif(btrim(canonical_name), '') is not null),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index entity_type_name_idx
  on core.entity (entity_type, lower(canonical_name));

create table core.entity_alias (
  id bigint generated always as identity primary key,
  entity_id uuid not null references core.entity(id) on delete restrict,
  alias text not null check (nullif(btrim(alias), '') is not null),
  normalized_alias text generated always as
    (lower(regexp_replace(btrim(alias), '\\s+', ' ', 'g'))) stored,
  alias_kind core.alias_kind not null,
  created_at timestamptz not null default now(),
  unique (entity_id, normalized_alias)
);

create table core.entity_alias_support (
  alias_id bigint not null references core.entity_alias(id) on delete restrict,
  claim_id uuid not null references public.claim(id) on delete restrict,
  primary key (alias_id, claim_id)
);
create index entity_alias_support_claim_idx
  on core.entity_alias_support (claim_id);

create table compute.organization (
  entity_id uuid primary key references core.entity(id) on delete restrict,
  organization_type compute.organization_type not null,
  website text check (website is null or website ~ '^https?://'),
  jurisdiction text
);

create table compute.place (
  entity_id uuid primary key references core.entity(id) on delete restrict,
  address text,
  county text,
  state text,
  country_code text not null check (country_code ~ '^[A-Z]{2}$'),
  geometry geometry(Geometry, 4326),
  geo_precision compute.geo_precision not null,
  check (geometry is null or st_isvalid(geometry))
);
create index place_geometry_idx on compute.place using gist (geometry);

create table compute.campus (
  entity_id uuid primary key references core.entity(id) on delete restrict,
  place_id uuid not null references compute.place(entity_id) on delete restrict,
  canonical_slug text not null unique
    check (canonical_slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$')
);
create index campus_place_idx on compute.campus (place_id);

create table compute.campus_phase (
  entity_id uuid primary key references core.entity(id) on delete restrict,
  campus_id uuid not null references compute.campus(entity_id) on delete restrict,
  phase_name text not null check (nullif(btrim(phase_name), '') is not null),
  unique (entity_id, campus_id),
  unique (campus_id, phase_name)
);
create index campus_phase_campus_idx on compute.campus_phase (campus_id);

create table compute.building (
  entity_id uuid primary key references core.entity(id) on delete restrict,
  campus_id uuid not null references compute.campus(entity_id) on delete restrict,
  phase_id uuid,
  building_name text not null check (nullif(btrim(building_name), '') is not null),
  foreign key (phase_id, campus_id)
    references compute.campus_phase(entity_id, campus_id) on delete restrict,
  unique (campus_id, building_name)
);
create index building_campus_idx on compute.building (campus_id);
create index building_phase_campus_idx on compute.building (phase_id, campus_id)
  where phase_id is not null;

create table compute.power_asset (
  entity_id uuid primary key references core.entity(id) on delete restrict,
  campus_id uuid not null references compute.campus(entity_id) on delete restrict,
  phase_id uuid,
  asset_type compute.power_asset_type not null,
  asset_name text,
  foreign key (phase_id, campus_id)
    references compute.campus_phase(entity_id, campus_id) on delete restrict
);
create index power_asset_campus_idx on compute.power_asset (campus_id);
create index power_asset_phase_campus_idx
  on compute.power_asset (phase_id, campus_id) where phase_id is not null;

create table compute.equipment_cohort (
  entity_id uuid primary key references core.entity(id) on delete restrict,
  power_asset_id uuid not null
    references compute.power_asset(entity_id) on delete restrict,
  cohort_name text not null check (nullif(btrim(cohort_name), '') is not null),
  unique (power_asset_id, cohort_name)
);
create index equipment_cohort_asset_idx
  on compute.equipment_cohort (power_asset_id);

create table core.fact_version (
  id uuid primary key default gen_random_uuid(),
  logical_id uuid not null default gen_random_uuid(),
  subject_entity_id uuid not null references core.entity(id) on delete restrict,
  fact_kind core.fact_kind not null,
  lineage_kind core.lineage_kind not null,
  valid_from date,
  valid_to date,
  recorded_at timestamptz not null default now(),
  verification_state core.verification_state not null,
  publication_state core.publication_state not null default 'candidate',
  supersedes_fact_id uuid,
  review_id uuid references public.review(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint fact_valid_range check (
    valid_to is null or (valid_from is not null and valid_to > valid_from)
  ),
  constraint fact_not_self_superseding check (
    supersedes_fact_id is null or supersedes_fact_id <> id
  ),
  constraint fact_published_has_review check (
    publication_state not in ('published', 'retracted') or review_id is not null
  ),
  unique (id, logical_id, subject_entity_id, fact_kind),
  foreign key (supersedes_fact_id, logical_id, subject_entity_id, fact_kind)
    references core.fact_version(id, logical_id, subject_entity_id, fact_kind)
    on delete restrict
);
create unique index fact_one_published_version_idx
  on core.fact_version (logical_id) where publication_state = 'published';
create unique index fact_one_staging_version_idx
  on core.fact_version (logical_id) where publication_state = 'staging';
create index fact_subject_kind_state_idx
  on core.fact_version (subject_entity_id, fact_kind, publication_state);
create index fact_supersedes_idx
  on core.fact_version (supersedes_fact_id, logical_id, subject_entity_id, fact_kind)
  where supersedes_fact_id is not null;
create index fact_review_idx on core.fact_version (review_id)
  where review_id is not null;

create table core.fact_support (
  id bigint generated always as identity primary key,
  fact_id uuid not null references core.fact_version(id) on delete restrict,
  support_kind core.support_kind not null,
  claim_id uuid references public.claim(id) on delete restrict,
  derivation text,
  created_at timestamptz not null default now(),
  constraint fact_support_shape check (
    (support_kind = 'direct' and claim_id is not null and derivation is null)
    or
    (support_kind = 'derived' and claim_id is null
      and nullif(btrim(derivation), '') is not null)
  )
);
create unique index fact_direct_support_once_idx
  on core.fact_support (fact_id, claim_id) where support_kind = 'direct';
create unique index fact_derived_support_once_idx
  on core.fact_support (fact_id) where support_kind = 'derived';
create index fact_support_fact_idx on core.fact_support (fact_id);
create index fact_support_claim_idx on core.fact_support (claim_id)
  where claim_id is not null;

create table core.fact_support_input (
  support_id bigint not null references core.fact_support(id) on delete restrict,
  input_fact_id uuid not null references core.fact_version(id) on delete restrict,
  primary key (support_id, input_fact_id)
);
create index fact_support_input_fact_idx
  on core.fact_support_input (input_fact_id);

create table compute.capacity_vocabulary (
  capacity_type text primary key,
  capacity_family compute.capacity_family not null,
  basis compute.capacity_basis not null,
  description text not null,
  unique (capacity_type, basis)
);

insert into compute.capacity_vocabulary
  (capacity_type, capacity_family, basis, description)
values
  ('utility_service_mw', 'utility_service', 'service_limit',
   'Utility-delivered service capacity at the declared scope.'),
  ('gross_generation_nameplate_mw', 'generation', 'gross_nameplate',
   'Gross nameplate generation capacity; not IT load.'),
  ('permitted_generation_mw', 'generation', 'permitted',
   'Generation capacity allowed by a permit; not observed operation.'),
  ('critical_it_mw', 'it', 'critical_it',
   'Critical IT load supported at the declared scope.'),
  ('contracted_it_mw', 'it', 'contracted_it',
   'IT capacity under a disclosed commercial contract.'),
  ('energized_it_mw', 'it', 'energized_it',
   'IT capacity with electrical service energized.'),
  ('occupied_it_mw', 'it', 'occupied_it',
   'IT capacity occupied by disclosed compute equipment or tenants.'),
  ('planned_it_mw', 'it', 'planned_it',
   'Forward-looking IT capacity announced or proposed.');

create table compute.status_vocabulary (
  status_axis compute.status_axis not null,
  status_value text not null check (status_value ~ '^[a-z0-9_]+$'),
  ordinal smallint not null check (ordinal > 0),
  terminal boolean not null default false,
  primary key (status_axis, status_value),
  unique (status_axis, ordinal)
);

insert into compute.status_vocabulary
  (status_axis, status_value, ordinal, terminal)
values
  ('site_control', 'rumored', 1, false),
  ('site_control', 'optioned', 2, false),
  ('site_control', 'acquired', 3, true),
  ('zoning', 'not_filed', 1, false),
  ('zoning', 'filed', 2, false),
  ('zoning', 'approved', 3, false),
  ('zoning', 'appealed', 4, true),
  ('environmental', 'not_filed', 1, false),
  ('environmental', 'filed', 2, false),
  ('environmental', 'draft', 3, false),
  ('environmental', 'issued', 4, false),
  ('environmental', 'challenged', 5, true),
  ('utility', 'requested', 1, false),
  ('utility', 'study', 2, false),
  ('utility', 'contracted', 3, false),
  ('utility', 'energized', 4, true),
  ('construction', 'clearing', 1, false),
  ('construction', 'shell', 2, false),
  ('construction', 'mep', 3, false),
  ('construction', 'commissioned', 4, true),
  ('compute', 'ordered', 1, false),
  ('compute', 'delivered', 2, false),
  ('compute', 'installed', 3, false),
  ('compute', 'serving', 4, true),
  ('commercial', 'marketed', 1, false),
  ('commercial', 'tenant_reported', 2, false),
  ('commercial', 'contracted', 3, true),
  ('finance', 'announced', 1, false),
  ('finance', 'committed', 2, false),
  ('finance', 'closed', 3, true);

create table compute.capacity_fact (
  fact_id uuid primary key references core.fact_version(id) on delete restrict,
  capacity_type text not null,
  capacity_basis compute.capacity_basis not null,
  qualifier compute.quantity_qualifier not null,
  value_mw numeric,
  lower_mw numeric,
  upper_mw numeric,
  scope_entity_id uuid not null references core.entity(id) on delete restrict,
  foreign key (capacity_type, capacity_basis)
    references compute.capacity_vocabulary(capacity_type, basis),
  constraint capacity_quantity_shape check (
    (
      qualifier = 'range'
      and value_mw is null
      and lower_mw is not null
      and upper_mw is not null
      and lower_mw <= upper_mw
    )
    or
    (
      qualifier <> 'range'
      and value_mw is not null
      and lower_mw is null
      and upper_mw is null
    )
  ),
  constraint capacity_nonnegative check (
    coalesce(value_mw, 0) >= 0
    and coalesce(lower_mw, 0) >= 0
    and coalesce(upper_mw, 0) >= 0
  )
);
create index capacity_scope_type_idx
  on compute.capacity_fact (scope_entity_id, capacity_type);
create index capacity_type_basis_idx
  on compute.capacity_fact (capacity_type, capacity_basis);

create table compute.status_fact (
  fact_id uuid primary key references core.fact_version(id) on delete restrict,
  status_axis compute.status_axis not null,
  status_value text not null,
  foreign key (status_axis, status_value)
    references compute.status_vocabulary(status_axis, status_value)
);
create index status_axis_value_idx
  on compute.status_fact (status_axis, status_value);

create table compute.relationship_fact (
  fact_id uuid primary key references core.fact_version(id) on delete restrict,
  object_entity_id uuid not null references core.entity(id) on delete restrict,
  relationship_type compute.relationship_type not null,
  role text
);
create index relationship_object_type_idx
  on compute.relationship_fact (object_entity_id, relationship_type);

create table compute.milestone_fact (
  fact_id uuid primary key references core.fact_version(id) on delete restrict,
  milestone_type compute.milestone_type not null,
  milestone_date date not null,
  date_precision compute.date_precision not null
);

create table compute.equipment_fact (
  fact_id uuid primary key references core.fact_version(id) on delete restrict,
  equipment_type text not null check (nullif(btrim(equipment_type), '') is not null),
  oem_entity_id uuid references core.entity(id) on delete restrict,
  model text,
  unit_count integer check (unit_count is null or unit_count > 0),
  mw_each numeric check (mw_each is null or mw_each >= 0),
  total_mw numeric check (total_mw is null or total_mw >= 0),
  basis compute.equipment_basis not null,
  constraint equipment_has_detail check (
    oem_entity_id is not null or nullif(btrim(model), '') is not null
    or unit_count is not null or mw_each is not null or total_mw is not null
  )
);
create index equipment_oem_idx on compute.equipment_fact (oem_entity_id)
  where oem_entity_id is not null;

create table compute.observation_fact (
  fact_id uuid primary key references core.fact_version(id) on delete restrict,
  observation_type compute.observation_type not null,
  observed_at timestamptz not null,
  value_text text,
  value_num numeric,
  value_json jsonb,
  unit text,
  geometry geometry(Geometry, 4326),
  constraint observation_one_value check (
    num_nonnulls(value_text, value_num, value_json) = 1
  ),
  constraint observation_numeric_unit check (
    value_num is null or nullif(btrim(unit), '') is not null
  ),
  constraint observation_geometry_valid check (
    geometry is null or st_isvalid(geometry)
  )
);
create index observation_time_idx
  on compute.observation_fact (observed_at desc);
create index observation_geometry_idx
  on compute.observation_fact using gist (geometry);

-- Typed subtypes are checked against the canonical entity/fact envelope.
create function core.enforce_entity_type()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  actual_type core.entity_type;
begin
  select e.entity_type into actual_type
  from core.entity e where e.id = new.entity_id;
  if actual_type is distinct from tg_argv[0]::core.entity_type then
    raise exception 'entity % is %, expected %', new.entity_id, actual_type, tg_argv[0]
      using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger organization_entity_type
  before insert or update of entity_id on compute.organization
  for each row execute function core.enforce_entity_type('organization');
create trigger place_entity_type
  before insert or update of entity_id on compute.place
  for each row execute function core.enforce_entity_type('place');
create trigger campus_entity_type
  before insert or update of entity_id on compute.campus
  for each row execute function core.enforce_entity_type('campus');
create trigger campus_phase_entity_type
  before insert or update of entity_id on compute.campus_phase
  for each row execute function core.enforce_entity_type('campus_phase');
create trigger building_entity_type
  before insert or update of entity_id on compute.building
  for each row execute function core.enforce_entity_type('building');
create trigger power_asset_entity_type
  before insert or update of entity_id on compute.power_asset
  for each row execute function core.enforce_entity_type('power_asset');
create trigger equipment_cohort_entity_type
  before insert or update of entity_id on compute.equipment_cohort
  for each row execute function core.enforce_entity_type('equipment_cohort');

create function core.enforce_fact_kind()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  actual_kind core.fact_kind;
begin
  select f.fact_kind into actual_kind
  from core.fact_version f where f.id = new.fact_id;
  if actual_kind is distinct from tg_argv[0]::core.fact_kind then
    raise exception 'fact % is %, expected %', new.fact_id, actual_kind, tg_argv[0]
      using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger capacity_fact_kind
  before insert or update of fact_id on compute.capacity_fact
  for each row execute function core.enforce_fact_kind('capacity');
create trigger status_fact_kind
  before insert or update of fact_id on compute.status_fact
  for each row execute function core.enforce_fact_kind('status');
create trigger relationship_fact_kind
  before insert or update of fact_id on compute.relationship_fact
  for each row execute function core.enforce_fact_kind('relationship');
create trigger milestone_fact_kind
  before insert or update of fact_id on compute.milestone_fact
  for each row execute function core.enforce_fact_kind('milestone');
create trigger equipment_fact_kind
  before insert or update of fact_id on compute.equipment_fact
  for each row execute function core.enforce_fact_kind('equipment');
create trigger observation_fact_kind
  before insert or update of fact_id on compute.observation_fact
  for each row execute function core.enforce_fact_kind('observation');

create function compute.enforce_nonreflexive_relationship()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  subject_id uuid;
begin
  select f.subject_entity_id into subject_id
  from core.fact_version f where f.id = new.fact_id;
  if subject_id = new.object_entity_id then
    raise exception 'relationship fact % cannot point to its own subject', new.fact_id
      using errcode = '23514';
  end if;
  return new;
end;
$$;

create trigger relationship_not_reflexive
  before insert or update of fact_id, object_entity_id on compute.relationship_fact
  for each row execute function compute.enforce_nonreflexive_relationship();

-- Fact versions are immutable records.  Only the publication state and an
-- initially-null review ID may advance in place.
create function core.preserve_fact_version_history()
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

create trigger preserve_fact_version_history
  before update or delete on core.fact_version
  for each row execute function core.preserve_fact_version_history();

create function core.preserve_fact_payload()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  target_fact_id uuid;
  target_state core.publication_state;
begin
  target_fact_id := case when tg_op = 'DELETE' then old.fact_id else new.fact_id end;
  select f.publication_state into target_state
  from core.fact_version f where f.id = target_fact_id;
  if target_state in ('published', 'retracted') then
    raise exception 'payload for % fact % is immutable', target_state, target_fact_id
      using errcode = '23514';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end;
$$;

create trigger preserve_capacity_payload
  before insert or update or delete on compute.capacity_fact
  for each row execute function core.preserve_fact_payload();
create trigger preserve_status_payload
  before insert or update or delete on compute.status_fact
  for each row execute function core.preserve_fact_payload();
create trigger preserve_relationship_payload
  before insert or update or delete on compute.relationship_fact
  for each row execute function core.preserve_fact_payload();
create trigger preserve_milestone_payload
  before insert or update or delete on compute.milestone_fact
  for each row execute function core.preserve_fact_payload();
create trigger preserve_equipment_payload
  before insert or update or delete on compute.equipment_fact
  for each row execute function core.preserve_fact_payload();
create trigger preserve_observation_payload
  before insert or update or delete on compute.observation_fact
  for each row execute function core.preserve_fact_payload();

create function core.preserve_fact_support()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  target_fact_id uuid;
  target_state core.publication_state;
begin
  target_fact_id := case when tg_op = 'DELETE' then old.fact_id else new.fact_id end;
  select f.publication_state into target_state
  from core.fact_version f where f.id = target_fact_id;
  if target_state in ('published', 'retracted') then
    raise exception 'support for % fact % is immutable', target_state, target_fact_id
      using errcode = '23514';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end;
$$;

create trigger preserve_fact_support
  before insert or update or delete on core.fact_support
  for each row execute function core.preserve_fact_support();

create function core.preserve_fact_support_input()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  target_support_id bigint;
  target_fact_id uuid;
  target_state core.publication_state;
  target_kind core.support_kind;
  target_input uuid;
begin
  target_support_id := case when tg_op = 'DELETE' then old.support_id else new.support_id end;
  target_input := case when tg_op = 'DELETE' then old.input_fact_id else new.input_fact_id end;
  select s.fact_id, s.support_kind, f.publication_state
    into target_fact_id, target_kind, target_state
  from core.fact_support s
  join core.fact_version f on f.id = s.fact_id
  where s.id = target_support_id;
  if target_kind <> 'derived' then
    raise exception 'only derived support may reference input facts'
      using errcode = '23514';
  end if;
  if target_input = target_fact_id then
    raise exception 'a derived fact cannot support itself' using errcode = '23514';
  end if;
  if target_state in ('published', 'retracted') then
    raise exception 'inputs for % fact % are immutable', target_state, target_fact_id
      using errcode = '23514';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end;
$$;

create trigger preserve_fact_support_input
  before insert or update or delete on core.fact_support_input
  for each row execute function core.preserve_fact_support_input();

create function core.assert_alias_supported(p_alias_id bigint)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if exists (select 1 from core.entity_alias a where a.id = p_alias_id)
     and not exists (
       select 1
       from core.entity_alias_support s
       join public.claim c on c.id = s.claim_id
       where s.alias_id = p_alias_id and c.status::text = 'validated'
     ) then
    raise exception 'entity alias % has no validated claim support', p_alias_id
      using errcode = '23514';
  end if;
end;
$$;

create function core.enforce_alias_support_trigger()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  target_alias_id bigint;
begin
  if tg_table_name = 'entity_alias' then
    if tg_op = 'DELETE' then
      target_alias_id := old.id;
    else
      target_alias_id := new.id;
    end if;
  else
    if tg_op = 'DELETE' then
      target_alias_id := old.alias_id;
    else
      target_alias_id := new.alias_id;
    end if;
  end if;
  perform core.assert_alias_supported(target_alias_id);
  return null;
end;
$$;

create constraint trigger entity_alias_requires_support
  after insert or update on core.entity_alias
  deferrable initially deferred
  for each row execute function core.enforce_alias_support_trigger();
create constraint trigger entity_alias_support_guard
  after insert or update or delete on core.entity_alias_support
  deferrable initially deferred
  for each row execute function core.enforce_alias_support_trigger();

create function core.assert_fact_ready(p_fact_id uuid)
returns void
language plpgsql
security invoker
set search_path = ''
as $$
declare
  f core.fact_version%rowtype;
  typed_row_exists boolean;
begin
  select * into f from core.fact_version where id = p_fact_id;
  if not found or f.publication_state <> 'published' then
    return;
  end if;

  typed_row_exists := case f.fact_kind
    when 'capacity' then exists (
      select 1 from compute.capacity_fact x where x.fact_id = f.id)
    when 'status' then exists (
      select 1 from compute.status_fact x where x.fact_id = f.id)
    when 'relationship' then exists (
      select 1 from compute.relationship_fact x where x.fact_id = f.id)
    when 'milestone' then exists (
      select 1 from compute.milestone_fact x where x.fact_id = f.id)
    when 'equipment' then exists (
      select 1 from compute.equipment_fact x where x.fact_id = f.id)
    when 'observation' then exists (
      select 1 from compute.observation_fact x where x.fact_id = f.id)
  end;
  if not typed_row_exists then
    raise exception 'published % fact % has no typed payload', f.fact_kind, f.id
      using errcode = '23514';
  end if;

  if f.lineage_kind = 'direct' then
    if exists (
      select 1 from core.fact_support s
      where s.fact_id = f.id and s.support_kind <> 'direct'
    ) or not exists (
      select 1
      from core.fact_support s
      join public.claim c on c.id = s.claim_id
      where s.fact_id = f.id
        and s.support_kind = 'direct'
        and c.status::text = 'validated'
    ) or exists (
      select 1
      from core.fact_support s
      join public.claim c on c.id = s.claim_id
      where s.fact_id = f.id
        and s.support_kind = 'direct'
        and c.status::text <> 'validated'
    ) then
      raise exception 'published direct fact % requires only validated claim support', f.id
        using errcode = '23514';
    end if;
  else
    if exists (
      select 1 from core.fact_support s
      where s.fact_id = f.id and s.support_kind <> 'derived'
    ) or not exists (
      select 1
      from core.fact_support s
      where s.fact_id = f.id
        and s.support_kind = 'derived'
        and nullif(btrim(s.derivation), '') is not null
        and exists (
          select 1
          from core.fact_support_input i
          join core.fact_version input on input.id = i.input_fact_id
          where i.support_id = s.id
            and input.publication_state = 'published'
        )
    ) then
      raise exception 'published derived fact % requires a formula and published input facts', f.id
        using errcode = '23514';
    end if;
  end if;
end;
$$;

create function core.enforce_fact_ready_trigger()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  target_fact_id uuid;
begin
  if tg_table_name = 'fact_version' then
    target_fact_id := case when tg_op = 'DELETE' then old.id else new.id end;
  elsif tg_table_name = 'fact_support' then
    target_fact_id := case when tg_op = 'DELETE' then old.fact_id else new.fact_id end;
  elsif tg_table_name = 'fact_support_input' then
    select s.fact_id into target_fact_id
    from core.fact_support s
    where s.id = case when tg_op = 'DELETE' then old.support_id else new.support_id end;
  else
    target_fact_id := case when tg_op = 'DELETE' then old.fact_id else new.fact_id end;
  end if;
  if target_fact_id is not null then
    perform core.assert_fact_ready(target_fact_id);
  end if;
  return null;
end;
$$;

create constraint trigger fact_version_truth_guard
  after insert or update on core.fact_version
  deferrable initially deferred
  for each row execute function core.enforce_fact_ready_trigger();
create constraint trigger fact_support_truth_guard
  after insert or update or delete on core.fact_support
  deferrable initially deferred
  for each row execute function core.enforce_fact_ready_trigger();
create constraint trigger fact_support_input_truth_guard
  after insert or update or delete on core.fact_support_input
  deferrable initially deferred
  for each row execute function core.enforce_fact_ready_trigger();
create constraint trigger capacity_fact_truth_guard
  after insert or update or delete on compute.capacity_fact
  deferrable initially deferred
  for each row execute function core.enforce_fact_ready_trigger();
create constraint trigger status_fact_truth_guard
  after insert or update or delete on compute.status_fact
  deferrable initially deferred
  for each row execute function core.enforce_fact_ready_trigger();
create constraint trigger relationship_fact_truth_guard
  after insert or update or delete on compute.relationship_fact
  deferrable initially deferred
  for each row execute function core.enforce_fact_ready_trigger();
create constraint trigger milestone_fact_truth_guard
  after insert or update or delete on compute.milestone_fact
  deferrable initially deferred
  for each row execute function core.enforce_fact_ready_trigger();
create constraint trigger equipment_fact_truth_guard
  after insert or update or delete on compute.equipment_fact
  deferrable initially deferred
  for each row execute function core.enforce_fact_ready_trigger();
create constraint trigger observation_fact_truth_guard
  after insert or update or delete on compute.observation_fact
  deferrable initially deferred
  for each row execute function core.enforce_fact_ready_trigger();

create view core.fact_evidence
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
  ) as input_fact_ids
from core.fact_version f
join core.fact_support s on s.fact_id = f.id
left join public.claim c on c.id = s.claim_id
left join public.document d on d.id = c.document_id
left join core.fact_support_input i on i.support_id = s.id
group by f.id, f.logical_id, f.fact_kind, f.publication_state,
  s.id, s.support_kind, s.derivation, c.id, c.document_id,
  d.url, d.sha256, d.r2_key, c.quote, c.page;

create view compute.current_capacity
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
  c.scope_entity_id
from core.fact_version f
join compute.capacity_fact c on c.fact_id = f.id
join compute.capacity_vocabulary v on v.capacity_type = c.capacity_type
where f.publication_state = 'published';

create function compute.sum_exact_capacity_mw(
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
  from compute.current_capacity c
  where c.capacity_type = p_capacity_type
    and c.scope_entity_id = p_scope_entity_id
    and c.qualifier = 'exact';
  return result;
end;
$$;

-- Operational schemas are private.  Public products consume generated
-- snapshots, never these tables or views directly.
do $$
declare
  table_row record;
begin
  for table_row in
    select schemaname, tablename
    from pg_tables
    where schemaname in ('core', 'compute')
  loop
    execute format('alter table %I.%I enable row level security',
      table_row.schemaname, table_row.tablename);
    execute format('alter table %I.%I force row level security',
      table_row.schemaname, table_row.tablename);
  end loop;
end;
$$;

revoke all on schema core, compute from public, anon, authenticated;
revoke all on all tables in schema core, compute from public, anon, authenticated;
revoke all on all sequences in schema core, compute from public, anon, authenticated;
revoke all on all functions in schema core, compute from public, anon, authenticated;

grant usage on schema core, compute to service_role;
grant select, insert, update, delete on all tables in schema core, compute to service_role;
grant usage, select on all sequences in schema core, compute to service_role;
grant execute on all functions in schema core, compute to service_role;

comment on schema core is
  'Shared private identity, temporal fact, evidence, and review primitives.';
comment on schema compute is
  'Private Compute Record domain entities, vocabularies, and typed fact payloads.';
comment on table core.fact_version is
  'Append-only fact version envelope. Corrections supersede; published rows are never edited.';
comment on table compute.capacity_fact is
  'Typed MW capacity. Types and scopes remain explicit; missing capacity is absence, never zero.';

commit;
