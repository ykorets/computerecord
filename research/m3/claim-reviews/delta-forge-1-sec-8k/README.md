# Delta Forge 1 anchored-claim review

This proposed packet is derived exclusively from the remote-verified complete
SEC submission captured for Applied Digital's 2026-04-23 8-K.

## Proposed source assertions

The packet validates six assertions at one structured XBRL anchor and three
short unique text anchors:

- registrant legal name: `APPLIED DIGITAL CORPORATION`;
- the registrant reports the `Delta Forge 1` campus;
- the filing locates it in Alexandria, Louisiana;
- the campus is described as currently under construction;
- the filing headline reports 430 MW.

Validation means only that the exact archived source contains the assertion.

## Proposed entity seeds

- organization: `Applied Digital Corporation`;
- city-level place: `Alexandria, Louisiana`;
- campus: `Applied Digital Delta Forge 1`, aliases `Delta Forge 1` and `DF1`.

All three remain proposed and no Postgres row is written.

## Blocked normalizations

The 430 MW headline does not identify one unambiguous capacity type or scope,
so no capacity fact is created. The construction assertion does not identify a
specific phase or building scope, so no typed status fact is created.

## Verify

Repository-only:

```bash
python3 -m engine.research.claims verify \
  --packet-dir research/m3/claim-reviews/delta-forge-1-sec-8k \
  --spec research/m3/claim-reviews/delta-forge-1-sec-8k/spec.json \
  --receipt research/m3/evidence-captures/2026-07-25/delta-forge-1-sec-8k/receipt.json
```

Archive-byte verification additionally supplies `--object-file` with the
downloaded private R2 object.
