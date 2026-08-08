# M5 identity-staging plan

This sealed plan combines the immutable Childress, Delta Forge 1, and Beacon
Point review decisions. It proposes no facts and performs no database writes.

The plan preserves all ten approved identity candidates, their exact validated
claim support, GitHub merge provenance, aliases, and within-batch dependencies.
It also evaluates only the explicit canonical constraints already present in
the deployed schema. It does not infer missing values or coerce unsupported
vocabulary.

Current result:

- 10 approved identity candidates;
- 5 compatible with the current canonical subtype requirements;
- 5 blocked from canonical rows pending a separate data review;
- zero capacity, status, relationship, or milestone facts;
- zero authorized database or promotion writes.

The five blockers are deliberate and visible in `plan.json`: two missing
organization types, two missing country codes, and one unsupported
`project_company` organization type. Resolving them requires evidence-backed
normalization or an explicit schema-vocabulary decision.

Reproduce the plan:

```bash
python3 -m engine.research.staging build \
  --packet-dir research/m3/claim-reviews/childress-sec-10q \
  --packet-dir research/m3/claim-reviews/delta-forge-1-sec-8k \
  --packet-dir research/m3/claim-reviews/beacon-point-sec-8k \
  --plan /tmp/identity-staging-plan.json
```

CI rebuilds the plan and requires byte-identical output. A later reviewed
transaction may stage exact approved rows, but this artifact cannot authorize
canonical insertion or publication.

## Reviewed database load

`load-manifest.json` is the separate, target-bound request to write this exact
plan to the private staging tables. It permits database writes only for the
staging operation and keeps canonical writes, fact creation, and promotion
disabled. The request becomes executable only after review and merge to
`main`.

`stage.sql` is generated from the reproduced plan and load manifest. It:

- takes a database advisory lock and runs in one transaction;
- loads the three reviewed inputs and all ten candidates with aliases,
  dependencies, blockers, and claim support;
- verifies the plan checksum and seals the batch;
- asserts that canonical entity and fact counts do not change;
- is replay-safe only for the same already-sealed batch and checksum.

Reproduce both load artifacts:

```bash
python3 -m engine.research.staging build-load \
  --packet-dir research/m3/claim-reviews/childress-sec-10q \
  --packet-dir research/m3/claim-reviews/delta-forge-1-sec-8k \
  --packet-dir research/m3/claim-reviews/beacon-point-sec-8k \
  --plan research/m5/identity-staging/plan.json \
  --load-manifest /tmp/identity-staging-load.json \
  --sql /tmp/identity-staging.sql \
  --target-project-ref txglwhwnmjtbijbgcpwd
```

Merging the load request does not resolve any canonical blockers. The five
blocked candidates require a separate data-review artifact before any
canonical promotion can be proposed.
