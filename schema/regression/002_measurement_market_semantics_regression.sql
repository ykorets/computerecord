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

select e.id as campus_id
from core.entity e
where e.canonical_name = 'Example Compute Campus'
  and e.entity_type = 'campus'
\gset

select c.place_id
from compute.campus c
where c.entity_id = :'campus_id'
\gset

select f.review_id
from core.fact_version f
where f.subject_entity_id = :'campus_id'
  and f.publication_state = 'published'
order by f.created_at
limit 1
\gset

select d.id as document_id
from public.document d
where d.url = 'https://example.test/source'
limit 1
\gset

insert into public.claim
  (document_id, entity_hint, field, value, value_num, unit, anchor,
   quote, match_score, numeric_check, confidence, extractor_version, status)
values
  (:'document_id', 'Example Compute Campus', 'capacity.forecast_mw',
   'Forecast critical IT capacity: 500 MW by 2029', 500, 'MW', 'quote',
   'Forecast critical IT capacity: 500 MW by 2029', 1.0, true, 1.0,
   'regression-v2', 'validated'),
  (:'document_id', 'Example Compute Campus', 'satellite.construction_activity',
   'Construction activity visible in the fixture scene', null, null, 'quote',
   'Construction activity visible in the fixture scene', 1.0, true, 1.0,
   'regression-v2', 'validated');

select id as forecast_claim_id from public.claim
where field = 'capacity.forecast_mw' and extractor_version = 'regression-v2'
\gset
select id as satellite_claim_id from public.claim
where field = 'satellite.construction_activity'
  and extractor_version = 'regression-v2'
\gset

select gen_random_uuid() as scenario_id,
       gen_random_uuid() as forecast_fact_id,
       gen_random_uuid() as observation_fact_id,
       gen_random_uuid() as market_id,
       gen_random_uuid() as infrastructure_id
\gset

select set_config('compute.regression.m21.campus_id', :'campus_id', false),
       set_config('compute.regression.m21.place_id', :'place_id', false),
       set_config('compute.regression.m21.review_id', :'review_id', false),
       set_config('compute.regression.m21.scenario_id', :'scenario_id', false),
       set_config('compute.regression.m21.forecast_fact_id', :'forecast_fact_id', false);

insert into compute.scenario
  (id, scenario_key, version, name, description, issued_at, review_id)
values
  (:'scenario_id', 'regression_outlook', 1, 'Regression outlook',
   'A deterministic scenario fixture for measurement-semantics regression.',
   '2026-08-05T00:00:00Z', :'review_id');

do $$
declare campus_id uuid := current_setting('compute.regression.m21.campus_id')::uuid;
declare review_id uuid := current_setting('compute.regression.m21.review_id')::uuid;
declare scenario_id uuid := current_setting('compute.regression.m21.scenario_id')::uuid;
begin
  begin
    insert into core.fact_version
      (subject_entity_id, fact_kind, lineage_kind, epistemic_type,
       verification_state, review_id, forecast_horizon)
    values
      (campus_id, 'capacity', 'direct', 'forecast', 'source_asserted',
       review_id, date '2029-12-31');
    raise exception 'expected forecast without vintage rejection';
  exception when check_violation then null;
  end;

  begin
    insert into core.fact_version
      (subject_entity_id, fact_kind, lineage_kind, epistemic_type,
       verification_state, review_id, scenario_id)
    values
      (campus_id, 'capacity', 'direct', 'reported', 'source_asserted',
       review_id, scenario_id);
    raise exception 'expected scenario on non-forecast rejection';
  exception when check_violation then null;
  end;
end;
$$;

begin;
insert into core.fact_version
  (id, subject_entity_id, fact_kind, lineage_kind, epistemic_type,
   period_start, period_end, issued_at, forecast_horizon, scenario_id,
   verification_state, review_id)
values
  (:'forecast_fact_id', :'campus_id', 'capacity', 'direct', 'forecast',
   date '2029-01-01', date '2029-12-31', '2026-08-05T00:00:00Z',
   date '2029-12-31', :'scenario_id', 'source_asserted', :'review_id');
insert into compute.capacity_fact
  (fact_id, capacity_type, capacity_basis, qualifier, value_mw, scope_entity_id)
values
  (:'forecast_fact_id', 'critical_it_mw', 'critical_it', 'exact', 500,
   :'campus_id');
insert into core.fact_support (fact_id, support_kind, claim_id)
values (:'forecast_fact_id', 'direct', :'forecast_claim_id');
update core.fact_version set publication_state = 'staging'
where id = :'forecast_fact_id';
update core.fact_version set publication_state = 'published'
where id = :'forecast_fact_id';
commit;

select pg_temp.assert_true(
  (select count(*) = 1 from compute.forecast_capacity
   where fact_id = :'forecast_fact_id' and value_mw = 500),
  'forecast capacity is explicit and queryable'
);
select pg_temp.assert_true(
  not exists (select 1 from compute.actual_capacity
              where fact_id = :'forecast_fact_id'),
  'forecast capacity cannot leak into actual capacity'
);
select pg_temp.assert_true(
  compute.sum_exact_capacity_mw('critical_it_mw', :'campus_id') = 120,
  'forecast capacity cannot inflate the actual aggregate'
);

do $$
declare forecast_fact_id uuid :=
  current_setting('compute.regression.m21.forecast_fact_id')::uuid;
begin
  begin
    update core.fact_version
    set epistemic_type = 'reported'
    where id = forecast_fact_id;
    raise exception 'expected immutable epistemic semantics';
  exception when check_violation then null;
  end;
end;
$$;

insert into core.entity (id, entity_type, canonical_name) values
  (:'market_id', 'market', 'Example Compute Metro'),
  (:'infrastructure_id', 'infrastructure_node', 'Example Grid Supply Point');
insert into compute.market
  (entity_id, place_id, market_type, methodology_version)
values (:'market_id', :'place_id', 'metro', 'regression-v1');
insert into compute.infrastructure_node
  (entity_id, place_id, node_type, stable_identifier)
values (:'infrastructure_id', :'place_id', 'grid_supply_point', 'GSP-TEST-1');

do $$
declare campus_id uuid := current_setting('compute.regression.m21.campus_id')::uuid;
declare place_id uuid := current_setting('compute.regression.m21.place_id')::uuid;
begin
  begin
    insert into compute.market
      (entity_id, place_id, market_type, methodology_version)
    values (campus_id, place_id, 'metro', 'regression-v1');
    raise exception 'expected market subtype mismatch';
  exception when check_violation then null;
  end;
end;
$$;

begin;
insert into core.fact_version
  (id, subject_entity_id, fact_kind, lineage_kind, epistemic_type,
   period_start, period_end, verification_state, review_id)
values
  (:'observation_fact_id', :'campus_id', 'observation', 'direct', 'observed',
   date '2026-08-05', date '2026-08-05', 'source_asserted', :'review_id');
insert into compute.observation_fact
  (fact_id, observation_type, observed_at, value_text)
values
  (:'observation_fact_id', 'construction_activity',
   '2026-08-05T15:00:00Z', 'foundation work visible');
insert into compute.satellite_observation
  (fact_id, provider, scene_identifier, acquired_at, resolution_m,
   cloud_cover_pct, license_code, redistribution_status, scene_geometry)
values
  (:'observation_fact_id', 'RegressionSat', 'SCENE-001',
   '2026-08-05T15:00:00Z', 0.5, 3, 'fixture-only', 'private_only',
   st_geomfromtext('POLYGON((-99.8 32.4,-99.6 32.4,-99.6 32.6,-99.8 32.6,-99.8 32.4))', 4326));
insert into core.fact_support (fact_id, support_kind, claim_id)
values (:'observation_fact_id', 'direct', :'satellite_claim_id');
update core.fact_version set publication_state = 'staging'
where id = :'observation_fact_id';
update core.fact_version set publication_state = 'published'
where id = :'observation_fact_id';
commit;

do $$
declare wrong_fact uuid := gen_random_uuid();
declare campus_id uuid := current_setting('compute.regression.m21.campus_id')::uuid;
declare review_id uuid := current_setting('compute.regression.m21.review_id')::uuid;
begin
  insert into core.fact_version
    (id, subject_entity_id, fact_kind, lineage_kind, epistemic_type,
     verification_state, review_id)
  values
    (wrong_fact, campus_id, 'observation', 'direct', 'observed',
     'source_asserted', review_id);
  insert into compute.observation_fact
    (fact_id, observation_type, observed_at, value_num, unit)
  values (wrong_fact, 'gas_flow', '2026-08-05T15:00:00Z', 10, 'mcf');
  begin
    insert into compute.satellite_observation
      (fact_id, provider, scene_identifier, acquired_at, resolution_m,
       license_code, redistribution_status)
    values
      (wrong_fact, 'RegressionSat', 'SCENE-WRONG',
       '2026-08-05T15:00:00Z', 1, 'fixture-only', 'private_only');
    raise exception 'expected non-satellite observation rejection';
  exception when check_violation then null;
  end;
end;
$$;

insert into compute.metric_definition
  (metric_key, version, name, description, unit, geography_type, formula,
   methodology, methodology_version, review_id)
values
  ('campus.actual_critical_it_mw', 1, 'Actual critical IT capacity',
   'Published non-forecast critical IT capacity for a campus.', 'MW',
   'campus', 'SUM(exact actual critical_it_mw facts)',
   'Include published critical_it_mw facts classified as reported, observed, administrative, or derived.',
   'regression-v1', :'review_id')
returning id as metric_definition_id
\gset

insert into compute.metric_definition_fact_kind
values (:'metric_definition_id', 'capacity');
insert into compute.metric_definition_epistemic_type values
  (:'metric_definition_id', 'reported'),
  (:'metric_definition_id', 'observed'),
  (:'metric_definition_id', 'administrative'),
  (:'metric_definition_id', 'derived');
insert into compute.metric_definition_capacity_type
values (:'metric_definition_id', 'critical_it_mw');

select f.id as actual_fact_id
from core.fact_version f
join compute.capacity_fact c on c.fact_id = f.id
where f.subject_entity_id = :'campus_id'
  and f.publication_state = 'published'
  and f.epistemic_type = 'reported'
  and c.capacity_type = 'critical_it_mw'
  and c.value_mw = 120
\gset

select set_config(
         'compute.regression.m21.metric_definition_id',
         :'metric_definition_id', false
       ),
       set_config(
         'compute.regression.m21.actual_fact_id', :'actual_fact_id', false
       );

insert into compute.metric_observation
  (metric_definition_id, subject_entity_id, period_start, period_end,
   issued_at, qualifier, value, coverage_numerator, coverage_denominator,
   uncertainty, review_id)
values
  (:'metric_definition_id', :'campus_id', date '2026-01-01',
   date '2026-12-31', '2026-08-05T18:00:00Z', 'exact', 120, 1, 1,
   'No quantified uncertainty in fixture.', :'review_id')
returning id as metric_observation_id
\gset

begin;
insert into compute.metric_observation_input
values (:'metric_observation_id', :'actual_fact_id');
update compute.metric_observation set publication_state = 'staging'
where id = :'metric_observation_id';
update compute.metric_observation set publication_state = 'published'
where id = :'metric_observation_id';
commit;

select pg_temp.assert_true(
  (select value = 120
          and input_fact_ids = array[:'actual_fact_id'::uuid]
          and coverage_numerator = 1
          and coverage_denominator = 1
   from compute.current_metric_observation
   where id = :'metric_observation_id'),
  'published metric exposes its exact input and coverage'
);

do $$
declare bad_metric uuid := gen_random_uuid();
declare metric_definition_id uuid :=
  current_setting('compute.regression.m21.metric_definition_id')::uuid;
declare campus_id uuid := current_setting('compute.regression.m21.campus_id')::uuid;
declare review_id uuid := current_setting('compute.regression.m21.review_id')::uuid;
declare forecast_fact_id uuid :=
  current_setting('compute.regression.m21.forecast_fact_id')::uuid;
begin
  begin
    insert into compute.metric_observation
      (id, metric_definition_id, subject_entity_id, period_start, period_end,
       issued_at, qualifier, value, review_id)
    values
      (bad_metric, metric_definition_id, campus_id, date '2029-01-01',
       date '2029-12-31', '2026-08-05T18:00:00Z', 'exact', 500, review_id);
    insert into compute.metric_observation_input
    values (bad_metric, forecast_fact_id);
    update compute.metric_observation set publication_state = 'staging'
    where id = bad_metric;
    update compute.metric_observation set publication_state = 'published'
    where id = bad_metric;
    set constraints all immediate;
    raise exception 'expected forecast input rejection for actual metric';
  exception when check_violation then null;
  end;
end;
$$;

do $$
declare empty_metric uuid := gen_random_uuid();
declare metric_definition_id uuid :=
  current_setting('compute.regression.m21.metric_definition_id')::uuid;
declare campus_id uuid := current_setting('compute.regression.m21.campus_id')::uuid;
declare review_id uuid := current_setting('compute.regression.m21.review_id')::uuid;
begin
  begin
    insert into compute.metric_observation
      (id, metric_definition_id, subject_entity_id, period_start, period_end,
       issued_at, qualifier, value, review_id)
    values
      (empty_metric, metric_definition_id, campus_id, date '2027-01-01',
       date '2027-12-31', '2026-08-05T18:00:00Z', 'exact', 0, review_id);
    update compute.metric_observation set publication_state = 'staging'
    where id = empty_metric;
    update compute.metric_observation set publication_state = 'published'
    where id = empty_metric;
    set constraints all immediate;
    raise exception 'expected input-free metric rejection';
  exception when check_violation then null;
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
  'all M2.1 operational tables have forced RLS'
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
  'every M2.1 foreign key has a supporting index'
);

select 'measurement and market semantics regression: ok' as result;
