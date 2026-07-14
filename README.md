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

## Current phase

`Data Foundation` — schema, source coverage, ingestion, evidence, temporal
facts, review, and public snapshots. The public site comes after the data path
works end to end.

## Public identity

- Product: **The Compute Record**
- Domain: **computerecord.com**
- Attribution: **by Yaro Korets**

