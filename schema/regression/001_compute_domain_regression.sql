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

insert into public.source (id, kind, url, adapter, schedule)
values ('compute-regression', 'pagehash', 'https://example.test/source',
        'regression', 'manual');

insert into public.document
  (source_id, url, r2_key, sha256, doc_genre)
values
  ('compute-regression', 'https://example.test/source',
   'docs/compute-regression.txt', repeat('a', 64), 'regression_fixture')
returning id as document_id \gset

insert into public.claim
  (document_id, entity_hint, field, value, value_num, unit, anchor,
   quote, match_score, numeric_check, confidence, extractor_version, status)
values
  (:'document_id', 'Example Compute Campus', 'entity.alias',
   'Example Compute Campus', null, null, 'quote',
   'Example Compute Campus', 1.0, true, 1.0, 'regression-v1', 'validated'),
  (:'document_id', 'Example Compute Campus', 'capacity.critical_it_mw',
   '100 MW critical IT', 100, 'MW', 'quote',
   '100 MW critical IT', 1.0, true, 1.0, 'regression-v1', 'validated'),
  (:'document_id', 'Example Compute Campus', 'capacity.utility_service_mw',
   '150 MW utility service', 150, 'MW', 'quote',
   '150 MW utility service', 1.0, true, 1.0, 'regression-v1', 'validated')
returning id, field;

select id as alias_claim_id from public.claim
  where field = 'entity.alias' \gset
select id as it_claim_id from public.claim
  where field = 'capacity.critical_it_mw' \gset
select id as utility_claim_id from public.claim
  where field = 'capacity.utility_service_mw' \gset
select review_id from public.btw_create_review_manifest(
  date '2026-07-14', '{}'::uuid[], '{}'::uuid[], '{}'::uuid[]
) \gset

select gen_random_uuid() as place_id,
       gen_random_uuid() as campus_id,
       gen_random_uuid() as empty_campus_id \gset

select set_config('compute.regression.campus_id', :'campus_id', false),
       set_config('compute.regression.review_id', :'review_id', false);

insert into core.entity (id, entity_type, canonical_name) values
  (:'place_id', 'place', 'Example Compute Campus place'),
  (:'campus_id', 'campus', 'Example Compute Campus'),
  (:'empty_campus_id', 'campus', 'Unknown-capacity campus');
insert into compute.place
  (entity_id, state, country_code, geometry, geo_precision)
values
  (:'place_id', 'TX', 'US', st_setsrid(st_makepoint(-99.7, 32.5), 4326), 'parcel');
insert into compute.campus (entity_id, place_id, canonical_slug) values
  (:'campus_id', :'place_id', 'example-compute-campus'),
  (:'empty_campus_id', :'place_id', 'unknown-capacity-campus');

begin;
insert into core.entity_alias (entity_id, alias, alias_kind)
values (:'campus_id', 'Example Compute DC', 'project')
returning id as alias_id \gset
insert into core.entity_alias_support (alias_id, claim_id)
values (:'alias_id', :'alias_claim_id');
commit;

do $$
declare campus_id uuid := current_setting('compute.regression.campus_id')::uuid;
begin
  begin
    insert into compute.organization (entity_id, organization_type)
    values (campus_id, 'operator');
    raise exception 'expected entity subtype mismatch';
  exception when check_violation then null;
  end;
end;
$$;

select gen_random_uuid() as it_fact_id, gen_random_uuid() as it_logical_id \gset
select set_config('compute.regression.it_fact_id', :'it_fact_id', false);
begin;
insert into core.fact_version
  (id, logical_id, subject_entity_id, fact_kind, lineage_kind,
   verification_state, review_id)
values
  (:'it_fact_id', :'it_logical_id', :'campus_id', 'capacity', 'direct',
   'source_asserted', :'review_id');
insert into compute.capacity_fact
  (fact_id, capacity_type, capacity_basis, qualifier, value_mw, scope_entity_id)
values
  (:'it_fact_id', 'critical_it_mw', 'critical_it', 'exact', 100, :'campus_id');
insert into core.fact_support (fact_id, support_kind, claim_id)
values (:'it_fact_id', 'direct', :'it_claim_id');
update core.fact_version set publication_state = 'staging' where id = :'it_fact_id';
update core.fact_version set publication_state = 'published' where id = :'it_fact_id';
commit;

select gen_random_uuid() as utility_fact_id, gen_random_uuid() as utility_logical_id \gset
select set_config('compute.regression.utility_fact_id', :'utility_fact_id', false);
begin;
insert into core.fact_version
  (id, logical_id, subject_entity_id, fact_kind, lineage_kind,
   verification_state, review_id)
values
  (:'utility_fact_id', :'utility_logical_id', :'campus_id', 'capacity', 'direct',
   'source_asserted', :'review_id');
insert into compute.capacity_fact
  (fact_id, capacity_type, capacity_basis, qualifier, value_mw, scope_entity_id)
values
  (:'utility_fact_id', 'utility_service_mw', 'service_limit', 'exact', 150,
   :'campus_id');
insert into core.fact_support (fact_id, support_kind, claim_id)
values (:'utility_fact_id', 'direct', :'utility_claim_id');
update core.fact_version set publication_state = 'staging'
  where id = :'utility_fact_id';
update core.fact_version set publication_state = 'published'
  where id = :'utility_fact_id';
commit;

select pg_temp.assert_true(
  compute.sum_exact_capacity_mw('critical_it_mw', :'campus_id') = 100,
  'critical IT capacity remains its own aggregate'
);
select pg_temp.assert_true(
  compute.sum_exact_capacity_mw('utility_service_mw', :'campus_id') = 150,
  'utility service capacity remains its own aggregate'
);
select pg_temp.assert_true(
  compute.sum_exact_capacity_mw('critical_it_mw', :'empty_campus_id') is null,
  'unknown capacity is NULL, not zero'
);

do $$
declare campus_id uuid := current_setting('compute.regression.campus_id')::uuid;
begin
  begin
    perform compute.sum_exact_capacity_mw(null, campus_id);
    raise exception 'expected a required capacity type';
  exception when null_value_not_allowed then null;
  end;
end;
$$;

do $$
declare bad_fact uuid := gen_random_uuid();
declare campus_id uuid := current_setting('compute.regression.campus_id')::uuid;
declare review_id uuid := current_setting('compute.regression.review_id')::uuid;
begin
  begin
    insert into core.fact_version
      (id, subject_entity_id, fact_kind, lineage_kind, verification_state, review_id)
    values
      (bad_fact, campus_id, 'capacity', 'direct', 'source_asserted', review_id);
    insert into compute.capacity_fact
      (fact_id, capacity_type, capacity_basis, qualifier, value_mw, scope_entity_id)
    values
      (bad_fact, 'critical_it_mw', 'service_limit', 'exact', 100, campus_id);
    raise exception 'expected incompatible capacity type/basis rejection';
  exception when foreign_key_violation then null;
  end;
end;
$$;

do $$
declare unsupported_fact uuid := gen_random_uuid();
declare campus_id uuid := current_setting('compute.regression.campus_id')::uuid;
declare review_id uuid := current_setting('compute.regression.review_id')::uuid;
begin
  begin
    insert into core.fact_version
      (id, subject_entity_id, fact_kind, lineage_kind, verification_state, review_id)
    values
      (unsupported_fact, campus_id, 'capacity', 'direct',
       'source_asserted', review_id);
    insert into compute.capacity_fact
      (fact_id, capacity_type, capacity_basis, qualifier, value_mw, scope_entity_id)
    values
      (unsupported_fact, 'critical_it_mw', 'critical_it', 'exact', 1, campus_id);
    update core.fact_version set publication_state = 'staging'
      where id = unsupported_fact;
    update core.fact_version set publication_state = 'published'
      where id = unsupported_fact;
    perform core.assert_fact_ready(unsupported_fact);
    raise exception 'expected unsupported publication rejection';
  exception when check_violation then null;
  end;
end;
$$;

select gen_random_uuid() as corrected_fact_id \gset
begin;
insert into core.fact_version
  (id, logical_id, subject_entity_id, fact_kind, lineage_kind,
   verification_state, supersedes_fact_id, review_id)
values
  (:'corrected_fact_id', :'it_logical_id', :'campus_id', 'capacity', 'direct',
   'corroborated', :'it_fact_id', :'review_id');
insert into compute.capacity_fact
  (fact_id, capacity_type, capacity_basis, qualifier, value_mw, scope_entity_id)
values
  (:'corrected_fact_id', 'critical_it_mw', 'critical_it', 'exact', 120,
   :'campus_id');
insert into core.fact_support (fact_id, support_kind, claim_id)
values (:'corrected_fact_id', 'direct', :'it_claim_id');
update core.fact_version set publication_state = 'staging'
  where id = :'corrected_fact_id';
update core.fact_version set publication_state = 'retracted'
  where id = :'it_fact_id';
update core.fact_version set publication_state = 'published'
  where id = :'corrected_fact_id';
commit;

select pg_temp.assert_true(
  (select count(*) = 2 from core.fact_version where logical_id = :'it_logical_id'),
  'a correction preserves both fact versions'
);
select pg_temp.assert_true(
  compute.sum_exact_capacity_mw('critical_it_mw', :'campus_id') = 120,
  'the corrected published version replaces the old aggregate input'
);
select pg_temp.assert_true(
  (select count(*) > 0 from core.fact_evidence
   where fact_id = :'corrected_fact_id' and claim_id = :'it_claim_id'),
  'published evidence is enumerable through real foreign keys'
);

do $$
declare old_fact_id uuid := current_setting('compute.regression.it_fact_id')::uuid;
begin
  begin
    delete from core.fact_version where id = old_fact_id;
    raise exception 'expected append-only history rejection';
  exception when check_violation then null;
  end;
end;
$$;

do $$
declare derived_fact uuid := gen_random_uuid();
declare derived_support bigint;
declare campus_id uuid := current_setting('compute.regression.campus_id')::uuid;
declare review_id uuid := current_setting('compute.regression.review_id')::uuid;
declare input_fact_id uuid := current_setting('compute.regression.utility_fact_id')::uuid;
begin
  insert into core.fact_version
    (id, subject_entity_id, fact_kind, lineage_kind, verification_state, review_id)
  values
    (derived_fact, campus_id, 'status', 'derived', 'corroborated', review_id);
  insert into compute.status_fact (fact_id, status_axis, status_value)
  values (derived_fact, 'utility', 'energized');
  insert into core.fact_support (fact_id, support_kind, derivation)
  values (derived_fact, 'derived',
          'Regression formula: published utility-service fact implies this fixture state.')
  returning id into derived_support;
  insert into core.fact_support_input (support_id, input_fact_id)
  values (derived_support, input_fact_id);
  update core.fact_version set publication_state = 'staging' where id = derived_fact;
  update core.fact_version set publication_state = 'published' where id = derived_fact;
end;
$$;

do $$
declare bad_status_fact uuid := gen_random_uuid();
declare campus_id uuid := current_setting('compute.regression.campus_id')::uuid;
declare review_id uuid := current_setting('compute.regression.review_id')::uuid;
begin
  begin
    insert into core.fact_version
      (id, subject_entity_id, fact_kind, lineage_kind, verification_state, review_id)
    values
      (bad_status_fact, campus_id, 'status', 'direct',
       'source_asserted', review_id);
    insert into compute.status_fact (fact_id, status_axis, status_value)
    values (bad_status_fact, 'utility', 'commissioned');
    raise exception 'expected invalid axis/value rejection';
  exception when foreign_key_violation then null;
  end;
end;
$$;

select pg_temp.assert_true(
  not exists (
    select 1
    from pg_class c
    join pg_namespace n on n.oid = c.relnamespace
    where n.nspname in ('core', 'compute')
      and c.relkind = 'r'
      and (not c.relrowsecurity or not c.relforcerowsecurity)
  ),
  'all operational tables have forced RLS'
);

select pg_temp.assert_true(
  not has_schema_privilege('anon', 'core', 'USAGE')
  and not has_schema_privilege('authenticated', 'compute', 'USAGE'),
  'operational schemas are not exposed to public API roles'
);

select pg_temp.assert_true(
  not exists (
    select 1
    from pg_constraint constraint_row
    where constraint_row.contype = 'f'
      and constraint_row.connamespace in ('core'::regnamespace, 'compute'::regnamespace)
      and not exists (
        select 1
        from pg_index index_row
        where index_row.indrelid = constraint_row.conrelid
          and index_row.indkey::smallint[] @> constraint_row.conkey
      )
  ),
  'every core/compute foreign key has a supporting index'
);

select 'compute domain regression: ok' as result;
