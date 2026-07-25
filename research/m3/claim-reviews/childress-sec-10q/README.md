# Childress anchored-claim review

This proposed review packet is derived exclusively from the exact SEC object
captured in the 2026-07-25 private evidence batch.

## Proposed source assertions

The packet contains six validated source assertions:

- SEC XBRL registrant legal name: `IREN Limited`;
- the registrant reports seven data-center sites;
- the reported site list includes `Childress`;
- Childress is reported in Texas, United States;
- the filing reports `750 MW` for Childress.

`validated` means the values are present at exact, unique anchors in the
archived object. It does not make them canonical Compute Record facts.

## Proposed entity seeds

- organization: `IREN Limited`;
- city-level place: `Childress, Texas, United States`;
- campus: `IREN Childress`, alias `Childress`.

All three remain `proposed`. The review packet does not write them to
Postgres.

## Capacity boundary

The 750 MW source assertion is retained, but fact normalization is blocked.
The filing describes total power capacity and refers to executed grid
connection agreements, letters of agreement, or equivalents. That does not
establish one unambiguous Compute Record capacity type or service scope.

No IT, energized, occupied, or utility-service capacity fact is created.

## Review behavior

The manifest pins:

- the private capture receipt and source SHA-256;
- the authored extraction specification;
- six deterministic claim IDs;
- three deterministic entity-candidate IDs;
- exact hashes of `claims.json` and `entity-seeds.json`.

PR #6 merged the packet at commit
`5edb1b9a9d3a3b30e081376f4a54d3a489aa5677`. The separate immutable
decision approves the three entity candidates only for a future staging
transaction. It does not promote rows or perform a database write. The
750 MW capacity normalization remains blocked.

## Verify

Repository-only verification:

```bash
python3 -m engine.research.claims verify \
  --packet-dir research/m3/claim-reviews/childress-sec-10q \
  --spec research/m3/claim-reviews/childress-sec-10q/spec.json \
  --receipt research/m3/evidence-captures/2026-07-25/childress-sec-10q/receipt.json
```

Archive-byte verification additionally supplies `--object-file` with the
downloaded private R2 object.

Decision verification:

```bash
python3 -m engine.research.decision verify \
  --spec research/m3/claim-reviews/childress-sec-10q/decision-spec.json \
  --review-manifest research/m3/claim-reviews/childress-sec-10q/review-manifest.json \
  --entity-seeds research/m3/claim-reviews/childress-sec-10q/entity-seeds.json \
  --decision research/m3/claim-reviews/childress-sec-10q/review-decision.json
```
