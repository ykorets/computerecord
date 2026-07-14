# Production database deployment

Production schema changes are deployed only from GitHub Actions after review
and merge to `main`. The workflow is manual, serialized, bound to the
`production` environment, and hard-guards the shared BTW project ref.

## One-time GitHub configuration

Add these encrypted environment secrets to `production`:

- `SUPABASE_ACCESS_TOKEN`
- `PRODUCTION_DB_PASSWORD`
- `PRODUCTION_PROJECT_ID` = `txglwhwnmjtbijbgcpwd`

Restrict the environment to the `main` branch. Never put credentials in the
repository, workflow inputs, artifacts, issue comments, or logs.

## Release

1. Confirm CI is green on the exact merge commit.
2. Run **deploy database** from `main`.
3. Enter `deploy-compute-001` as the confirmation.
4. Review the dry-run and migration-history artifacts.
5. Run the external Supabase security/performance advisors and the
   post-deployment audit queries.

The workflow is replay-safe. If the migration committed but a later audit
step failed, rerunning it performs a no-op push and repeats verification.

The migration is a single SQL transaction and takes an advisory lock. An
error before commit rolls back the whole change. After commit, use a reviewed
forward-only migration; do not drop the shared schemas as a rollback.
