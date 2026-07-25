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

## Queue baseline

- 49 unresolved campus tasks;
- 195 unverified discovery leads;
- 15 P0 tasks with an SEC filing lead;
- 6 P1 tasks with a government-record lead but no SEC filing lead;
- 28 P2 tasks whose available hints are organization publications;
- at queue seal time: 0 captured documents and 0 entity seeds.

Priority describes research order, not truth quality. The reported source type
is retained only as a hint from the benchmark. Capture progress is recorded in
separate, immutable
[`evidence-captures`](../evidence-captures/2026-07-25/README.md) batches so this
input queue remains reproducible.

Current state is not written back into this sealed baseline. The generated
[`progress.json`](../progress.json) overlays immutable capture receipts and
review decisions, so historical queue counts remain reproducible while current
coverage is accurate.

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
