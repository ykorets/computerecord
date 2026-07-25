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
- [Evidence capture runbook](docs/runbooks/evidence-capture.md)
- [Anchored claim review runbook](docs/runbooks/claim-review.md)
- [M3 coverage benchmark](benchmarks/neocloud-buildout-registry/2026-07-14/README.md)
- [M3 primary-source intake](research/m3/primary-source-intake/README.md)
- [First M3 evidence capture](research/m3/evidence-captures/2026-07-25/README.md)
- [Childress claim review](research/m3/claim-reviews/childress-sec-10q/README.md)
- [Primary-source registry](sources/README.md)

## Current phase

`Data Foundation · M3` — the Compute domain schema is implemented and
regression-tested; production application awaits the protected GitHub
credentials. The first 50-campus coverage benchmark is sealed and compared
against the pinned BTW public mirror. Its 49 unresolved campuses now have a
sealed, reproducible primary-source intake queue; every entity seed remains
blocked until independent evidence is captured. The first independently
discovered Childress SEC filing is now preserved in the shared private archive
with a byte-verified receipt. Six anchored source assertions and three entity
seeds passed GitHub review; an immutable decision approves the seeds only for
future staging. The ambiguous 750 MW capacity normalization remains blocked.
No database row or canonical fact has been created. The public site still
waits for an end-to-end published data path.

Database migrations live in `supabase/migrations/`. Production schema
deployment is manual and runs only through the protected GitHub workflow.

## Public identity

- Product: **The Compute Record**
- Domain: **computerecord.com**
- Attribution: **by Yaro Korets**
