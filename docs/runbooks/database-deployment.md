# Production database deployment

Production schema changes are deployed only from GitHub Actions after review
and merge to `main`. The workflow is manual, serialized, bound to the
`production` environment, and hard-guards the shared BTW project ref.

## One-time GitHub configuration

Add these encrypted environment secrets to `production`:

- `SUPABASE_ACCESS_TOKEN`
- `PRODUCTION_PROJECT_ID` = `txglwhwnmjtbijbgcpwd`

Restrict the environment to the `main` branch. Never put credentials in the
repository, workflow inputs, artifacts, issue comments, or logs.

The access token must belong to a project member and include the Management
API permissions needed to administer Temporary Access. The workflow enables
Temporary Access, maps that user to the existing `postgres` role for 90 days,
and renews the mapping on each deployment. The token is also used as the
temporary database password, so the long-lived Postgres password never needs
to be copied into GitHub. GitHub-hosted runner addresses are dynamic, therefore
the mapping has no IP allowlist; the token, protected environment, `main`-only
rule, explicit confirmation, and serialized job are the access controls.

## Release

1. Confirm CI is green on the exact merge commit.
2. Run **deploy database** from `main`.
3. Enter `deploy-compute-002` as the confirmation.
4. Review the dry-run and migration-history artifacts.
5. Run the external Supabase security/performance advisors and the
   post-deployment audit queries.

The workflow is replay-safe. If the migration committed but a later audit
step failed, rerunning it performs a no-op push and repeats verification.

The migration is a single SQL transaction and takes an advisory lock. An
error before commit rolls back the whole change. After commit, use a reviewed
forward-only migration; do not drop the shared schemas as a rollback.
