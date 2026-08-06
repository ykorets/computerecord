-- The Compute Record · M5 sealed identity staging
-- Private, immutable landing zone for reviewed identity candidates.
-- This migration intentionally provides no path to core.entity or facts.

begin;

set local lock_timeout = '10s';
set local statement_timeout = '180s';
select pg_advisory_xact_lock(
  hashtextextended('computerecord:database-migrations', 0)
);

set local search_path = public, extensions, core, compute;

create type core.identity_staging_state as enum ('loading', 'sealed');

create table core.identity_staging_batch (
  id uuid primary key,
  plan_sha256 text not null unique
    check (plan_sha256 ~ '^[0-9a-f]{64}$'),
  classification text not null
    check (classification = 'sealed_identity_staging_plan'),
  expected_review_packets integer not null check (expected_review_packets > 0),
  expected_identity_candidates integer not null
    check (expected_identity_candidates > 0),
  expected_canonical_ready integer not null check (expected_canonical_ready >= 0),
  expected_canonical_blocked integer not null
    check (expected_canonical_blocked >= 0),
  expected_blocker_count integer not null check (expected_blocker_count >= 0),
  state core.identity_staging_state not null default 'loading',
  created_at timestamptz not null default now(),
  sealed_at timestamptz,
  constraint identity_staging_expected_candidate_partition check (
    expected_identity_candidates =
      expected_canonical_ready + expected_canonical_blocked
  ),
  constraint identity_staging_expected_blockers_cover_blocked check (
    expected_blocker_count >= expected_canonical_blocked
  ),
  constraint identity_staging_batch_state_shape check (
    (state = 'loading' and sealed_at is null)
    or (state = 'sealed' and sealed_at is not null)
  )
);

create table core.identity_staging_input (
  batch_id uuid not null references core.identity_staging_batch(id)
    on delete restrict,
  packet_key text not null
    check (packet_key ~ '^[a-z0-9]+([_-][a-z0-9]+)*$'),
  review_id uuid not null,
  decision_id uuid not null,
  merge_commit text not null check (merge_commit ~ '^[0-9a-f]{40}$'),
  claims_sha256 text not null check (claims_sha256 ~ '^[0-9a-f]{64}$'),
  entity_seeds_sha256 text not null
    check (entity_seeds_sha256 ~ '^[0-9a-f]{64}$'),
  review_manifest_sha256 text not null
    check (review_manifest_sha256 ~ '^[0-9a-f]{64}$'),
  review_decision_sha256 text not null
    check (review_decision_sha256 ~ '^[0-9a-f]{64}$'),
  primary key (batch_id, decision_id),
  unique (batch_id, packet_key)
);

create table core.identity_staging_candidate (
  batch_id uuid not null references core.identity_staging_batch(id)
    on delete restrict,
  candidate_id uuid not null,
  candidate_key text not null
    check (candidate_key ~ '^[a-z0-9]+([_-][a-z0-9]+)*$'),
  entity_type core.entity_type not null,
  canonical_name text not null
    check (nullif(btrim(canonical_name), '') is not null),
  proposed_attributes jsonb not null default '{}'::jsonb
    check (jsonb_typeof(proposed_attributes) = 'object'),
  canonical_blockers text[] not null default '{}'::text[]
    check (array_position(canonical_blockers, null) is null),
  source_decision_id uuid not null,
  primary key (batch_id, candidate_id),
  unique (batch_id, candidate_key),
  foreign key (batch_id, source_decision_id)
    references core.identity_staging_input(batch_id, decision_id)
    on delete restrict
);
create index identity_staging_candidate_decision_idx
  on core.identity_staging_candidate (batch_id, source_decision_id);

create table core.identity_staging_alias (
  batch_id uuid not null,
  candidate_id uuid not null,
  alias text not null check (nullif(btrim(alias), '') is not null),
  normalized_alias text generated always as (
    lower(regexp_replace(btrim(alias), '[[:space:]]+', ' ', 'g'))
  ) stored,
  primary key (batch_id, candidate_id, normalized_alias),
  foreign key (batch_id, candidate_id)
    references core.identity_staging_candidate(batch_id, candidate_id)
    on delete restrict
);

create table core.identity_staging_support (
  batch_id uuid not null,
  candidate_id uuid not null,
  claim_id uuid not null,
  primary key (batch_id, candidate_id, claim_id),
  foreign key (batch_id, candidate_id)
    references core.identity_staging_candidate(batch_id, candidate_id)
    on delete restrict
);
create index identity_staging_support_claim_idx
  on core.identity_staging_support (claim_id);

create table core.identity_staging_dependency (
  batch_id uuid not null,
  candidate_id uuid not null,
  dependency_candidate_id uuid not null,
  primary key (batch_id, candidate_id, dependency_candidate_id),
  foreign key (batch_id, candidate_id)
    references core.identity_staging_candidate(batch_id, candidate_id)
    on delete restrict,
  foreign key (batch_id, dependency_candidate_id)
    references core.identity_staging_candidate(batch_id, candidate_id)
    on delete restrict,
  constraint identity_staging_dependency_not_self check (
    candidate_id <> dependency_candidate_id
  )
);
create index identity_staging_dependency_target_idx
  on core.identity_staging_dependency (batch_id, dependency_candidate_id);

create function core.guard_identity_staging_batch()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    if new.state <> 'loading' or new.sealed_at is not null then
      raise exception 'identity staging batches must start in loading state'
        using errcode = '23514';
    end if;
    return new;
  end if;

  if tg_op = 'DELETE' then
    raise exception 'identity staging batches are immutable'
      using errcode = '55000';
  end if;

  if new.id is distinct from old.id
     or new.plan_sha256 is distinct from old.plan_sha256
     or new.classification is distinct from old.classification
     or new.expected_review_packets is distinct from old.expected_review_packets
     or new.expected_identity_candidates is distinct from old.expected_identity_candidates
     or new.expected_canonical_ready is distinct from old.expected_canonical_ready
     or new.expected_canonical_blocked is distinct from old.expected_canonical_blocked
     or new.expected_blocker_count is distinct from old.expected_blocker_count
     or new.created_at is distinct from old.created_at
     or old.state <> 'loading'
     or new.state <> 'sealed'
     or new.sealed_at is null
     or current_setting('compute.identity_staging_seal', true)
        is distinct from old.id::text then
    raise exception 'identity staging batch transition is not authorized'
      using errcode = '55000';
  end if;
  return new;
end;
$$;

create trigger identity_staging_batch_guard
  before insert or update or delete on core.identity_staging_batch
  for each row execute function core.guard_identity_staging_batch();

create function core.guard_identity_staging_child()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
declare
  target_batch_id uuid;
begin
  if tg_op <> 'INSERT' then
    raise exception 'sealed identity staging rows are append-only'
      using errcode = '55000';
  end if;

  target_batch_id := new.batch_id;
  perform 1
  from core.identity_staging_batch b
  where b.id = target_batch_id and b.state = 'loading'
  for update;
  if not found then
    raise exception 'identity staging batch % is absent or sealed', target_batch_id
      using errcode = '55000';
  end if;
  return new;
end;
$$;

create trigger identity_staging_input_guard
  before insert or update or delete on core.identity_staging_input
  for each row execute function core.guard_identity_staging_child();
create trigger identity_staging_candidate_guard
  before insert or update or delete on core.identity_staging_candidate
  for each row execute function core.guard_identity_staging_child();
create trigger identity_staging_alias_guard
  before insert or update or delete on core.identity_staging_alias
  for each row execute function core.guard_identity_staging_child();
create trigger identity_staging_support_guard
  before insert or update or delete on core.identity_staging_support
  for each row execute function core.guard_identity_staging_child();
create trigger identity_staging_dependency_guard
  before insert or update or delete on core.identity_staging_dependency
  for each row execute function core.guard_identity_staging_child();

create function core.seal_identity_staging_batch(
  p_batch_id uuid,
  p_plan_sha256 text
)
returns uuid
language plpgsql
security invoker
set search_path = ''
as $$
declare
  batch_row core.identity_staging_batch%rowtype;
  actual_review_packets integer;
  actual_identity_candidates integer;
  actual_canonical_ready integer;
  actual_canonical_blocked integer;
  actual_blocker_count integer;
begin
  if p_batch_id is null or p_plan_sha256 is null then
    raise exception 'batch id and plan sha256 are required'
      using errcode = '22004';
  end if;

  select * into batch_row
  from core.identity_staging_batch b
  where b.id = p_batch_id
  for update;
  if not found then
    raise exception 'identity staging batch % does not exist', p_batch_id
      using errcode = '22023';
  end if;
  if batch_row.plan_sha256 <> p_plan_sha256 then
    raise exception 'identity staging plan checksum mismatch'
      using errcode = '22023';
  end if;
  if batch_row.state = 'sealed' then
    return batch_row.id;
  end if;

  select count(*)::integer into actual_review_packets
  from core.identity_staging_input i where i.batch_id = p_batch_id;

  select
    count(*)::integer,
    count(*) filter (where cardinality(c.canonical_blockers) = 0)::integer,
    count(*) filter (where cardinality(c.canonical_blockers) > 0)::integer,
    coalesce(sum(cardinality(c.canonical_blockers)), 0)::integer
  into actual_identity_candidates, actual_canonical_ready,
       actual_canonical_blocked, actual_blocker_count
  from core.identity_staging_candidate c
  where c.batch_id = p_batch_id;

  if actual_review_packets <> batch_row.expected_review_packets
     or actual_identity_candidates <> batch_row.expected_identity_candidates
     or actual_canonical_ready <> batch_row.expected_canonical_ready
     or actual_canonical_blocked <> batch_row.expected_canonical_blocked
     or actual_blocker_count <> batch_row.expected_blocker_count then
    raise exception 'identity staging batch % does not match its sealed counts',
      p_batch_id using errcode = '23514';
  end if;

  if exists (
    select 1
    from core.identity_staging_candidate c
    where c.batch_id = p_batch_id
      and not exists (
        select 1 from core.identity_staging_support s
        where s.batch_id = c.batch_id and s.candidate_id = c.candidate_id
      )
  ) then
    raise exception 'every identity candidate requires at least one support claim'
      using errcode = '23514';
  end if;

  perform set_config('compute.identity_staging_seal', p_batch_id::text, true);
  update core.identity_staging_batch
  set state = 'sealed', sealed_at = clock_timestamp()
  where id = p_batch_id;
  return p_batch_id;
end;
$$;

alter table core.identity_staging_batch enable row level security;
alter table core.identity_staging_batch force row level security;
alter table core.identity_staging_input enable row level security;
alter table core.identity_staging_input force row level security;
alter table core.identity_staging_candidate enable row level security;
alter table core.identity_staging_candidate force row level security;
alter table core.identity_staging_alias enable row level security;
alter table core.identity_staging_alias force row level security;
alter table core.identity_staging_support enable row level security;
alter table core.identity_staging_support force row level security;
alter table core.identity_staging_dependency enable row level security;
alter table core.identity_staging_dependency force row level security;

revoke all on table
  core.identity_staging_batch,
  core.identity_staging_input,
  core.identity_staging_candidate,
  core.identity_staging_alias,
  core.identity_staging_support,
  core.identity_staging_dependency
from public, anon, authenticated;
revoke all on function core.guard_identity_staging_batch()
  from public, anon, authenticated;
revoke all on function core.guard_identity_staging_child()
  from public, anon, authenticated;
revoke all on function core.seal_identity_staging_batch(uuid, text)
  from public, anon, authenticated;

grant select, insert, update on core.identity_staging_batch to service_role;
grant select, insert on table
  core.identity_staging_input,
  core.identity_staging_candidate,
  core.identity_staging_alias,
  core.identity_staging_support,
  core.identity_staging_dependency
to service_role;
grant execute on function core.seal_identity_staging_batch(uuid, text)
  to service_role;

comment on table core.identity_staging_batch is
  'Checksum-bound staging batches. Sealing does not authorize canonical or fact writes.';
comment on table core.identity_staging_candidate is
  'Reviewed candidate identities, including fail-closed rows with canonical blockers.';
comment on table core.identity_staging_support is
  'Reviewed claim identifiers from sealed packets. No claim FK exists until those packets are independently loaded and verified.';
comment on function core.seal_identity_staging_batch(uuid, text) is
  'Validates batch completeness and makes staging rows immutable; it performs no promotion.';

commit;
