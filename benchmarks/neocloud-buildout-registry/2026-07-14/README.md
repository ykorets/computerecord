# Neocloud Buildout Registry benchmark · 2026-07-14

This directory is a non-canonical coverage benchmark. It is not a source of
Compute Record facts and cannot feed publication or promotion.

## Capture receipt

- Classification: benchmark_only
- Captured at: 2026-07-14T18:16:23Z
- Public page:
  https://neocloudgroup.com/buildout-registry
- Landing-page SHA-256:
  650c527b7755cb7448c22ad6538f271d8aa76bc179fba946c76ecefba4aa9b85
- Public registry-response SHA-256:
  b8ed89d07638b00f6c87da1971aa242c132dd248c6ba04a4e6a0c77a94b77288
- Normalized targets SHA-256:
  df8247a481bd1d3ef9e4fc047eae0d4b9d965fe766bb852400aff5d4aa425ced
- Targets: 50 across 24 states

The repository does not redistribute the raw HTML or API payload. It retains
their hashes and a normalized factual target index. Competitor capacity values
are deliberately excluded. Source links are discovery leads, not evidence.

## Files

- manifest.json — capture time, request URLs, hashes, rights boundary.
- targets.json — target identity, location, reported stage, field presence,
  and explicitly classified discovery leads.
- resolution.json — deterministic candidates and explicit resolution state
  for every target.
- gap-report.json — gaps by campus, state, source class, and missing field.

## Current comparison

The comparison is pinned to BTW mirror commit
d5ccb766ad6630784b9de38837948f87e692d94e.

- 1 target resolves to an existing BTW identity:
  Stargate Abilene -> crusoe-stargate-abilene.
- 49 targets remain unresolved.
- The separate Crusoe Abilene AI Factory Campus (Microsoft) row is retained
  as unresolved; similarity to Stargate Abilene is a candidate, not sufficient
  identity evidence.
- 147 competitor-labeled primary leads cover all 50 targets.
- 50 competitor-labeled secondary leads cover 28 targets.

These labels describe the competitor's registry. The linked documents still
need independent capture, source classification, claim extraction, and review.

## Reproduce

    python3 -m engine.benchmarks.neocloud resolve \
      --targets benchmarks/neocloud-buildout-registry/2026-07-14/targets.json \
      --facilities _deps/btw-mirror/data/facilities.json \
      --announcements _deps/btw-mirror/data/announcements.json \
      --btw-mirror-commit d5ccb766ad6630784b9de38837948f87e692d94e \
      --output-dir /tmp/rebuilt-benchmark

    python3 -m engine.benchmarks.neocloud verify \
      --artifact-dir benchmarks/neocloud-buildout-registry/2026-07-14 \
      --expected-count 50

CI rebuilds resolution.json and gap-report.json from the pinned mirror and
requires byte-identical output.
