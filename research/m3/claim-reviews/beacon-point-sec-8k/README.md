# Beacon Point anchored-claim review

This proposed packet is derived exclusively from the remote-verified complete
SEC submission captured for Hut 8's 2026-06-10 8-K.

## Proposed source assertions

Eight assertions are validated at one XBRL anchor and five short unique text
anchors:

- registrant legal name: `HUT 8 CORPORATION`;
- project issuer: `Beacon Point DC LLC`;
- the issuer is reported as an indirect wholly owned Hut 8 subsidiary;
- the project is a data center comprising six data halls;
- combined critical IT capacity is reported as 352 MW;
- the property is in Nueces County, Texas.

Validation means only that the exact archived source contains the assertion.

## Proposed entity seeds

- organization: `Hut 8 Corporation`;
- project company: `Beacon Point DC LLC`;
- county-level place: `Nueces County, Texas`;
- campus: `Beacon Point`.

PR #17 reviewed the packet. The separate immutable decision approves all four
identity candidates only for a future staging transaction. No Postgres row is
written.

## Capacity semantics

Unlike the ambiguous Childress and Delta Forge headlines, this filing
explicitly identifies the measure as a combined total of 352 MW of critical IT
capacity across six data halls. The source assertion is therefore eligible for
later typed normalization as `critical_it_mw` with a development/planned basis.

This packet still creates no fact. Scope assignment, staging, review, and
promotion remain separate steps.

The decision does not normalize the 352 MW assertion. It remains eligible for
a separate typed fact review after the ADR-002 measurement semantics are
implemented.

## Verify

```bash
python3 -m engine.research.claims verify \
  --packet-dir research/m3/claim-reviews/beacon-point-sec-8k \
  --spec research/m3/claim-reviews/beacon-point-sec-8k/spec.json \
  --receipt research/m3/evidence-captures/2026-07-25/beacon-point-sec-8k/receipt.json
```

Archive-byte verification additionally supplies `--object-file` with the
downloaded private R2 object.

Decision verification:

```bash
python3 -m engine.research.decision verify \
  --spec research/m3/claim-reviews/beacon-point-sec-8k/decision-spec.json \
  --review-manifest research/m3/claim-reviews/beacon-point-sec-8k/review-manifest.json \
  --entity-seeds research/m3/claim-reviews/beacon-point-sec-8k/entity-seeds.json \
  --decision research/m3/claim-reviews/beacon-point-sec-8k/review-decision.json
```
