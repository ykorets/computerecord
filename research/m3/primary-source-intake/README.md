# M3 primary-source intake

This directory is the deterministic research queue for the 49 unresolved
campuses in the sealed 2026-07-14 coverage benchmark.

It is deliberately **not** an evidence archive and contains no Compute Record
facts. Competitor-provided links remain
`unverified_benchmark_discovery_lead` records. They may help a researcher find
an authoritative source, but they cannot support a claim, create an entity, or
enter publication.

## Queue contract

Every task starts with:

- `evidence_state: not_captured`;
- `entity_seed_state: blocked_pending_independent_evidence`;
- independent source rediscovery required;
- an immutable raw-document capture required before extraction;
- a rights and redistribution decision required before any public evidence
  copy.

The queue is pinned to the exact SHA-256 hashes of `targets.json` and
`resolution.json`. CI rebuilds `queue.json` and `report.json` and requires
byte-identical output.

## Current workload

- 49 unresolved campus tasks;
- 195 unverified discovery leads;
- 15 P0 tasks with an SEC filing lead;
- 6 P1 tasks with a government-record lead but no SEC filing lead;
- 28 P2 tasks whose available hints are organization publications;
- 0 captured documents and 0 entity seeds.

Priority describes research order, not truth quality. The reported source type
is retained only as a hint from the benchmark.

## Required next transition

For each task:

```text
benchmark hint
  -> independently rediscovered official URL
  -> immutable private archive object
  -> document receipt and rights decision
  -> anchored identity claim
  -> reviewed entity-resolution decision
  -> entity seed
```

The first capture batch should take the P0 queue through the archive and claim
stages without importing any competitor values.

## Reproduce

```bash
python3 -m engine.research.intake build \
  --targets benchmarks/neocloud-buildout-registry/2026-07-14/targets.json \
  --resolution benchmarks/neocloud-buildout-registry/2026-07-14/resolution.json \
  --output-dir /tmp/rebuilt-intake

python3 -m engine.research.intake verify \
  --artifact-dir research/m3/primary-source-intake \
  --targets benchmarks/neocloud-buildout-registry/2026-07-14/targets.json \
  --resolution benchmarks/neocloud-buildout-registry/2026-07-14/resolution.json \
  --expected-tasks 49
```
