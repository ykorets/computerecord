# Compute production baseline v1

This receipt records the first production deployment of the Compute Record
schemas. It is an audit reference, not a credential source or a substitute for
the migration files.

## Outcome

- Deployed: 2026-08-06 04:13 UTC
- Repository commit: `662b3ee0a955fb0455af79c21faac766fa8679ba`
- GitHub workflow: [`deploy database` run 31070641415](https://github.com/ykorets/computerecord/actions/runs/31070641415)
- Supabase project: `txglwhwnmjtbijbgcpwd` (`btw`)
- Organization: `KPI Creatives`, Pro
- Region: `us-east-1`
- Project state after deployment: `ACTIVE_HEALTHY`
- PostgreSQL build: `17.6.1.141`, release channel `ga`

The workflow used the pinned Supabase CLI `2.109.1`. It authenticated with the
protected Management API token and a short-lived CLI login role. No database
password was stored in GitHub.

## Reviewed migrations

The dry run identified exactly these pending migrations:

1. `20260714180000_compute_domain.sql`
2. `20260805210924_measurement_market_semantics.sql`

Both checksums matched their reviewed manifests before connection. Both
migrations were applied, and the final migration ledger records both local and
remote versions as equal. The post-deploy dry run and database lint completed
successfully. The workflow artifact retains the before ledger, exact dry run,
and after ledger for 90 days.

## Read-only structural audit

The independent post-deploy audit found:

| Schema | Tables | Views | Tables with RLS |
|---|---:|---:|---:|
| `core` | 6 | 1 | 6 |
| `compute` | 25 | 4 | 25 |

- `anon` and `authenticated` have no `USAGE` privilege on either schema.
- Neither role has table grants in `core` or `compute`.
- All five views have `security_invoker=true`.
- `compute.capacity_vocabulary` contains its eight reviewed rows.
- `compute.status_vocabulary` contains its 30 reviewed rows.
- All other Compute tables contain zero rows at this baseline.

The empty operational tables are intentional. Schema deployment did not
authorize entity staging, fact publication, a snapshot, or a website.

## Advisor interpretation

Supabase reported informational `rls_enabled_no_policy` notices for all 31 new
tables. This is the intended fail-closed posture: the public API roles have no
schema access or table grants, and no public read policy exists yet.

The one security error reported by the project advisor is the pre-existing
`public.llm_cost_weekly` security-definer view. It belongs to the BTW baseline,
was not created or modified by these migrations, and is outside this receipt's
authorized change scope. See the Supabase
[`security_definer_view` remediation](https://supabase.com/docs/guides/database/database-linter?lint=0010_security_definer_view).

Unused-index and unindexed-foreign-key notices are expected before operational
data and query telemetry exist. Index removal or addition requires observed
workload evidence and a separate reviewed migration.

## Next gate

The next authorized step is sprint 5 in the roadmap: stage the ten identity
candidates already approved by immutable review decisions. Staging must remain
separate from publication and must not create capacity or status facts.
