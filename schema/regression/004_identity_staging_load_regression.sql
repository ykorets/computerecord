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

select count(*) as entity_count_before from core.entity
\gset
select count(*) as fact_count_before from core.fact_version
\gset

\ir ../../research/m5/identity-staging/stage.sql
\ir ../../research/m5/identity-staging/stage.sql

select pg_temp.assert_true(
  (select state = 'sealed'
          and plan_sha256 = 'a75762db08e915835df63c5dacdd7228bfa8e831d6f713313e0405e33322587e'
   from core.identity_staging_batch
   where id = '0e19f055-e1a9-5153-b7fd-e28be6a0ebff'),
  'the exact reviewed batch is sealed'
);
select pg_temp.assert_true(
  (select count(*) = 3 from core.identity_staging_input
   where batch_id = '0e19f055-e1a9-5153-b7fd-e28be6a0ebff'),
  'all three reviewed packets are staged'
);
select pg_temp.assert_true(
  (select count(*) = 10 from core.identity_staging_candidate
   where batch_id = '0e19f055-e1a9-5153-b7fd-e28be6a0ebff'),
  'all ten reviewed candidates are staged exactly once'
);
select pg_temp.assert_true(
  (select count(*) = 5 from core.identity_staging_candidate
   where batch_id = '0e19f055-e1a9-5153-b7fd-e28be6a0ebff'
     and cardinality(canonical_blockers) = 0),
  'five candidates remain canonical-ready'
);
select pg_temp.assert_true(
  (select count(*) = 5 from core.identity_staging_candidate
   where batch_id = '0e19f055-e1a9-5153-b7fd-e28be6a0ebff'
     and cardinality(canonical_blockers) > 0),
  'five candidates remain fail-closed for data review'
);
select pg_temp.assert_true(
  (select count(*) = 8 from core.identity_staging_alias
   where batch_id = '0e19f055-e1a9-5153-b7fd-e28be6a0ebff')
  and
  (select count(*) = 28 from core.identity_staging_support
   where batch_id = '0e19f055-e1a9-5153-b7fd-e28be6a0ebff')
  and
  (select count(*) = 3 from core.identity_staging_dependency
   where batch_id = '0e19f055-e1a9-5153-b7fd-e28be6a0ebff'),
  'aliases, claim support, and dependencies are complete'
);
select pg_temp.assert_true(
  (select count(*) from core.entity) = :'entity_count_before'::bigint
  and (select count(*) from core.fact_version) = :'fact_count_before'::bigint,
  'staging and replay create no canonical entities or facts'
);
