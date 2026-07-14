-- EXTERNAL BASELINE: ykorets/btw. See docs/baselines/btw-supabase-history.md.
do $$ begin
  raise exception 'missing external BTW migration 20260713225658';
end $$;
