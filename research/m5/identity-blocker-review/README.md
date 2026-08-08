# M5 identity blocker data review

This separate review examines the five canonical blockers in the sealed
production staging batch. It does not edit the approved source packets, clear
any blocker, write canonical rows, create facts, or authorize promotion.

The review finds three distinct resolution routes:

- two place candidates need a versioned state-to-country normalization source;
- two organizations need additional primary evidence that explicitly states
  their role at the named campus;
- one project-specific LLC needs an explicit schema-vocabulary decision.

In particular, the review refuses to label a company `operator` merely because
it filed an SEC document, and refuses to coerce `project_company` to `other`.
The proposed `US` patches for Louisiana and Texas remain proposals until a
reviewed subdivision crosswalk is added to the engine and a later decision is
merged.

Reproduce the review:

```bash
python3 -m engine.research.identity_blocker_review build \
  --spec research/m5/identity-blocker-review/spec.json \
  --plan research/m5/identity-staging/plan.json \
  --load-manifest research/m5/identity-staging/load-manifest.json \
  --production-receipt research/m5/identity-staging/production-receipt.json \
  --stage-sql research/m5/identity-staging/stage.sql \
  --output /tmp/identity-blocker-review.json
```

CI verifies the exact five-candidate set, evidence links, staging receipt, and
review-only policy before comparing the rebuilt artifact byte for byte.
