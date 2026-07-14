# BTW Supabase migration history

Compute Record shares the production database with Behind the Watt but does
not own BTW's migrations. The nine versions listed in
`deploy/manifests/001_compute_domain.json` are an immutable external
baseline observed in project `txglwhwnmjtbijbgcpwd` before the first Compute
Record deployment.

The matching files under `supabase/migrations/` are guards, not copies of
BTW schema SQL. Supabase compares migration histories by timestamp, so the
files allow the CLI to reconcile an already-applied baseline. Every guard
raises an exception if its timestamp is missing on the target. This prevents
Compute Record from pretending that a missing BTW migration was applied.

The canonical BTW schema remains pinned and regression-tested through
`docs/baselines/btw-mirror-v1.md`. A new BTW database must be built by BTW
first; the Compute Record migration must never bootstrap it.
