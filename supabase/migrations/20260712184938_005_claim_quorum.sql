-- EXTERNAL BASELINE: ykorets/btw. See docs/baselines/btw-supabase-history.md.
do $$ begin
  raise exception 'missing external BTW migration 20260712184938';
end $$;
