# Production database deployment

Since 2026-11-06 the shared BTW / Compute Record database is the owned
PostgreSQL 17 + PostGIS instance `btw-postgres` on the Korets VPS
(database `btw`, schemas `public`, `core`, `compute`). The former Supabase
project `txglwhwnmjtbijbgcpwd` is retired; the Supabase CLI deployment
workflow was removed. The database has no public port, so GitHub Actions
cannot reach it directly.

## Release

1. Merge the reviewed migration to `main` with CI green (CI applies every
   migration to a fresh PostgreSQL in the runner).
2. In a session with the owner, apply the exact merged file on the VPS
   (Coolify terminal → localhost):

   ```sh
   docker exec -i btw-postgres psql -U postgres -d btw -v ON_ERROR_STOP=1 \
     --single-transaction < supabase/migrations/<file>.sql
   ```

3. Record the file, its sha256 and the migration receipt in
   `docs/baselines/`, and note the change in the infrastructure record
   (`ykorets/infrastructure`).
4. Run the post-deployment audit queries.

A nightly offsite backup of the database is kept in R2
(`btw-db-backups/nightly/`); check that last night's backup succeeded before
applying a migration.

Each migration is a single SQL transaction and takes an advisory lock. An
error before commit rolls back the whole change. After commit, use a reviewed
forward-only migration; do not drop the shared schemas as a rollback.

## Production baseline

The first production deployment and its independent audit are recorded in
[`compute-production-v1.md`](../baselines/compute-production-v1.md). Future
schema releases append a new receipt; they do not rewrite that baseline.
