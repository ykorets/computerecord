# The Compute Record

**The evidence-backed record of data-center buildout.**

The Compute Record is an independent research and data product by **Yaro
Korets**. It tracks data-center campuses from announcement through permits,
construction, energization, and compute operation, with every published fact
connected to preserved evidence.

The website is a read-only projection of the database. It is never a second
source of truth and never contains hand-maintained factual values.

## Product rule

```text
Source -> Archive -> Claim -> Review -> Published fact -> Snapshot -> Website
```

If a value has not passed through this path, it is not a Compute Record fact.

## Relationship to Behind the Watt

The Compute Record and Behind the Watt are sibling products by Yaro Korets.
They have separate brands and public interfaces while sharing an evidence
engine, immutable source archive, review discipline, and publication model.

- **Behind the Watt:** behind-the-meter power, permits, equipment, fuel, and
  operating verification.
- **The Compute Record:** campuses, phases, buildings, power delivery, IT
  capacity, tenants, construction, capital, and supply chain.

## Documentation

- [Target architecture](docs/architecture.md)
- [ADR-001: shared evidence platform](docs/adr/ADR-001-shared-evidence-platform.md)
- [Data Foundation roadmap](docs/roadmap.md)
- [Production database deployment](docs/runbooks/database-deployment.md)
- [M3 coverage benchmark](benchmarks/neocloud-buildout-registry/2026-07-14/README.md)

## Current phase

`Data Foundation · M3` — the Compute domain schema is implemented and
regression-tested; production application awaits the protected GitHub
credentials. The first 50-campus coverage benchmark is sealed and compared
against the pinned BTW public mirror. Independent primary-source capture comes
next. The public site still waits for an end-to-end published data path.

Database migrations live in `supabase/migrations/`. Production schema
deployment is manual and runs only through the protected GitHub workflow.

## Public identity

- Product: **The Compute Record**
- Domain: **computerecord.com**
- Attribution: **by Yaro Korets**
