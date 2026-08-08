\set ON_ERROR_STOP on
set search_path = public, extensions, core, compute;

create function pg_temp.assert_true(condition boolean, message text)
returns void language plpgsql as $$
begin
  if condition is not true then
    raise exception 'assertion failed: %', message;
  end if;
end;
$$;

begin;

create temporary table identity_staging_baseline as
select
  (select count(*) from core.entity) as entity_count,
  (select count(*) from core.fact_version) as fact_count;

select gen_random_uuid() as batch_id,
       gen_random_uuid() as decision_id,
       gen_random_uuid() as ready_candidate_id,
       gen_random_uuid() as blocked_candidate_id,
       gen_random_uuid() as claim_one_id,
       gen_random_uuid() as claim_two_id
\gset

insert into core.identity_staging_batch (
  id, plan_sha256, classification, expected_review_packets,
  expected_identity_candidates, expected_canonical_ready,
  expected_canonical_blocked, expected_blocker_count
) values (
  :'batch_id', repeat('a', 64), 'sealed_identity_staging_plan', 1,
  2, 1, 1, 1
);

insert into core.identity_staging_input (
  batch_id, packet_key, review_id, decision_id, merge_commit,
  claims_sha256, entity_seeds_sha256, review_manifest_sha256,
  review_decision_sha256
) values (
  :'batch_id', 'regression-packet', gen_random_uuid(), :'decision_id',
  repeat('b', 40), repeat('c', 64), repeat('d', 64), repeat('e', 64),
  repeat('f', 64)
);

insert into core.identity_staging_candidate (
  batch_id, candidate_id, candidate_key, entity_type, canonical_name,
  proposed_attributes, canonical_blockers, source_decision_id
) values
  (:'batch_id', :'ready_candidate_id', 'organization-ready', 'organization',
   'Ready Organization', '{"organization_type":"operator"}', '{}',
   :'decision_id'),
  (:'batch_id', :'blocked_candidate_id', 'place-blocked', 'place',
   'Blocked Place', '{}', array['missing_country_code'], :'decision_id');

insert into core.identity_staging_alias (batch_id, candidate_id, alias) values
  (:'batch_id', :'ready_candidate_id', '  Ready   Organization  '),
  (:'batch_id', :'blocked_candidate_id', 'Blocked Place');
insert into core.identity_staging_support (batch_id, candidate_id, claim_id)
values
  (:'batch_id', :'ready_candidate_id', :'claim_one_id'),
  (:'batch_id', :'blocked_candidate_id', :'claim_two_id');
insert into core.identity_staging_dependency (
  batch_id, candidate_id, dependency_candidate_id
) values (:'batch_id', :'blocked_candidate_id', :'ready_candidate_id');

select pg_temp.assert_true(
  (select normalized_alias = 'ready organization'
   from core.identity_staging_alias
   where batch_id = :'batch_id' and candidate_id = :'ready_candidate_id'),
  'aliases are normalized deterministically'
);
select pg_temp.assert_true(
  core.seal_identity_staging_batch(:'batch_id', repeat('a', 64)) = :'batch_id',
  'a complete checksum-bound batch seals'
);
select pg_temp.assert_true(
  (select state = 'sealed' and sealed_at is not null
   from core.identity_staging_batch where id = :'batch_id'),
  'sealed state records its timestamp'
);
select pg_temp.assert_true(
  core.seal_identity_staging_batch(:'batch_id', repeat('a', 64)) = :'batch_id',
  'sealing is replay-safe for the same checksum'
);

select set_config('compute.regression.m5.batch_id', :'batch_id', false),
       set_config(
         'compute.regression.m5.ready_candidate_id',
         :'ready_candidate_id', false
       );

do $$
declare
  v_batch_id uuid := current_setting('compute.regression.m5.batch_id')::uuid;
  v_ready_candidate_id uuid :=
    current_setting('compute.regression.m5.ready_candidate_id')::uuid;
begin
  begin
    perform core.seal_identity_staging_batch(v_batch_id, repeat('0', 64));
    raise exception 'expected checksum mismatch';
  exception when sqlstate '22023' then null;
  end;

  begin
    update core.identity_staging_batch
    set expected_identity_candidates = 3 where id = v_batch_id;
    raise exception 'expected immutable batch rejection';
  exception when sqlstate '55000' then null;
  end;

  begin
    update core.identity_staging_candidate c set canonical_name = 'Changed'
    where c.batch_id = v_batch_id
      and c.candidate_id = v_ready_candidate_id;
    raise exception 'expected immutable candidate rejection';
  exception when sqlstate '55000' then null;
  end;

  begin
    insert into core.identity_staging_support
      (batch_id, candidate_id, claim_id)
    values (v_batch_id, v_ready_candidate_id, gen_random_uuid());
    raise exception 'expected post-seal insert rejection';
  exception when sqlstate '55000' then null;
  end;

  begin
    delete from core.identity_staging_batch where id = v_batch_id;
    raise exception 'expected immutable batch delete rejection';
  exception when sqlstate '55000' then null;
  end;
end;
$$;

do $$
declare
  incomplete_batch_id uuid := gen_random_uuid();
  incomplete_decision_id uuid := gen_random_uuid();
  incomplete_candidate_id uuid := gen_random_uuid();
begin
  insert into core.identity_staging_batch (
    id, plan_sha256, classification, expected_review_packets,
    expected_identity_candidates, expected_canonical_ready,
    expected_canonical_blocked, expected_blocker_count
  ) values (
    incomplete_batch_id, repeat('1', 64), 'sealed_identity_staging_plan',
    1, 1, 1, 0, 0
  );
  insert into core.identity_staging_input (
    batch_id, packet_key, review_id, decision_id, merge_commit,
    claims_sha256, entity_seeds_sha256, review_manifest_sha256,
    review_decision_sha256
  ) values (
    incomplete_batch_id, 'unsupported-regression-packet', gen_random_uuid(),
    incomplete_decision_id, repeat('2', 40), repeat('3', 64),
    repeat('4', 64), repeat('5', 64), repeat('6', 64)
  );
  insert into core.identity_staging_candidate (
    batch_id, candidate_id, candidate_key, entity_type, canonical_name,
    source_decision_id
  ) values (
    incomplete_batch_id, incomplete_candidate_id, 'unsupported-candidate',
    'organization', 'Unsupported Candidate', incomplete_decision_id
  );
  begin
    perform core.seal_identity_staging_batch(incomplete_batch_id, repeat('1', 64));
    raise exception 'expected unsupported candidate rejection';
  exception when check_violation then null;
  end;
end;
$$;

select pg_temp.assert_true(
  (select count(*) = 6
   from pg_class c join pg_namespace n on n.oid = c.relnamespace
   where n.nspname = 'core'
     and c.relname like 'identity_staging_%'
     and c.relkind = 'r'
     and c.relrowsecurity and c.relforcerowsecurity),
  'every identity staging table has forced RLS'
);
select pg_temp.assert_true(
  not has_table_privilege('anon', 'core.identity_staging_batch', 'select')
  and not has_table_privilege(
    'authenticated', 'core.identity_staging_candidate', 'select'
  ),
  'browser roles have no staging table privileges'
);
select pg_temp.assert_true(
  not has_function_privilege(
    'anon', 'core.seal_identity_staging_batch(uuid,text)', 'execute'
  ) and not (
    select p.prosecdef
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'core' and p.proname = 'seal_identity_staging_batch'
  ),
  'sealing is private and security invoker'
);
select pg_temp.assert_true(
  (select b.entity_count = (select count(*) from core.entity)
          and b.fact_count = (select count(*) from core.fact_version)
   from identity_staging_baseline b),
  'identity staging cannot create canonical entities or facts'
);

rollback;
