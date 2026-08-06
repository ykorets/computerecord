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
