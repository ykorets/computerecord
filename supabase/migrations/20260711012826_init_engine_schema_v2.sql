-- EXTERNAL BASELINE: ykorets/btw.
-- This timestamp must already exist in the target migration history.
-- It deliberately fails if the Compute Record repository is asked to fake it.
do $$ begin
  raise exception 'missing external BTW migration 20260711012826';
end $$;
