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

Merging the PR requests an approval decision. It does not promote rows or
perform a database write. A later decision artifact must record the merge
commit before any atomic promotion.

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
