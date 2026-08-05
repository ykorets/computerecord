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
- [ADR-002: measurement and market semantics](docs/adr/ADR-002-measurement-and-market-semantics.md)
- [Data Foundation roadmap](docs/roadmap.md)
- [Production database deployment](docs/runbooks/database-deployment.md)
- [Evidence capture runbook](docs/runbooks/evidence-capture.md)
- [Anchored claim review runbook](docs/runbooks/claim-review.md)
- [M3 coverage benchmark](benchmarks/neocloud-buildout-registry/2026-07-14/README.md)
- [M3 primary-source intake](research/m3/primary-source-intake/README.md)
- [First M3 evidence capture](research/m3/evidence-captures/2026-07-25/README.md)
- [Childress claim review](research/m3/claim-reviews/childress-sec-10q/README.md)
- [Delta Forge 1 claim review](research/m3/claim-reviews/delta-forge-1-sec-8k/README.md)
- [Beacon Point claim review](research/m3/claim-reviews/beacon-point-sec-8k/README.md)
- [Primary-source registry](sources/README.md)
- [Current M3 research progress](research/m3/progress.json)

## Current phase

`Data Foundation · M2.1/M3/M4` — the core Compute schema and additive
measurement semantics are implemented and regression-tested; production
application awaits the guarded GitHub deployment and protected credentials.
The 50-campus benchmark and 49-task independent intake queue are sealed. Childress,
Delta Forge 1, and
Beacon Point have private byte-verified SEC captures, anchored claims, and
immutable review decisions approving ten identity candidates for future
staging while three unsafe Childress/Delta Forge normalizations remain blocked.
Beacon Point's 352 MW is explicitly reported as combined critical IT capacity
across six data halls and remains eligible for a separate typed normalization
review after M2.1. Ten Tier-1 SEC watchers now have a deterministic schedule,
recorded health, and a discovery adapter. No database row, canonical fact,
public snapshot, or Compute site has been created.

Database migrations live in `supabase/migrations/`. Production schema
deployment is manual and runs only through the protected GitHub workflow.

## Public identity

- Product: **The Compute Record**
- Domain: **computerecord.com**
- Attribution: **by Yaro Korets**
