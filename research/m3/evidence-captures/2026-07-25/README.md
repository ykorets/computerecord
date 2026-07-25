# M3 evidence capture batch · 2026-07-25

This batch contains the first independently discovered source document for an
unresolved Compute Record benchmark target.

## Childress SEC 10-Q

- Target: `neocloud-buildout-registry:childress`
- Intake task: `m3-primary-source-intake:childress`
- Publisher: U.S. Securities and Exchange Commission
- Source:
  https://www.sec.gov/Archives/edgar/data/1878848/000187884826000026/iren-20260331.htm
- Discovery: direct SEC EDGAR search; this URL was not copied from the
  benchmark discovery leads
- Captured: `2026-07-25T00:54:07Z`
- Size: 1,959,789 bytes
- Source SHA-256:
  `3d59f51f926263a28997dc3647d97dd9312febcb7a4611e809bcfc498dcafd27`
- Private archive:
  `r2://btw-docs/docs/3d59f51f926263a28997dc3647d97dd9312febcb7a4611e809bcfc498dcafd27.html`

The source bytes were uploaded to the shared private R2 archive, downloaded
again, and accepted only after the downloaded object matched the retrieval
SHA-256 and byte size.

## Current boundary

This batch proves document capture only:

- captured documents: 1;
- extracted claims: 0;
- entity seeds: 0;
- public evidence copies: 0.

The receipt is fail-closed as
`private_only_pending_review`. The original publisher URL remains the Source.
The private archive object must not be exposed merely because the source is a
public filing.

Anchored identity and location assertions are now proposed in the
[Childress claim-review packet](../../claim-reviews/childress-sec-10q/README.md).
They remain unpromoted until the review decision is recorded.

## Delta Forge 1 complete SEC submission

The second immutable batch independently rediscovered Applied Digital's
2026-04-23 8-K through its official SEC submissions endpoint and filing index.
It captures the SEC complete-submission text, not the exhibit URL present in
the benchmark hints.

- Target: `neocloud-buildout-registry:apld-delta-forge-1-alexandria-la`
- Intake task: `m3-primary-source-intake:apld-delta-forge-1-alexandria-la`
- Captured: `2026-07-25T23:00:49Z`
- Size: 8,382,819 bytes
- Source SHA-256:
  `5e6628dd2c0a151eb5b321585449843bb355ea576759fe6739de4b40c23aacb3`
- Private archive:
  `r2://btw-docs/docs/5e6628dd2c0a151eb5b321585449843bb355ea576759fe6739de4b40c23aacb3.txt`

The complete submission contains the 8-K, the furnished Delta Forge 1 press
release, and other filing exhibits. Exact bytes were uploaded to private R2,
downloaded again, and hash-matched before the receipt was sealed. No claim,
entity, capacity fact, or public evidence copy is created by this capture.

## Beacon Point complete SEC submission

The third immutable batch independently rediscovered Hut 8's 2026-06-10 8-K
through the official SEC submissions endpoint. It captures the complete
submission text rather than the primary-document URL present in the benchmark
hints.

- Target: `neocloud-buildout-registry:hut8-beacon-point-tx`
- Intake task: `m3-primary-source-intake:hut8-beacon-point-tx`
- Captured: `2026-07-25T23:11:16Z`
- Size: 1,761,948 bytes
- Source SHA-256:
  `f547559e83c5b13c230bb1f7a6625da4ba423470223bcf973c17f6539e82a0ed`
- Private archive:
  `r2://btw-docs/docs/f547559e83c5b13c230bb1f7a6625da4ba423470223bcf973c17f6539e82a0ed.txt`

The complete submission contains Hut 8's 8-K and the project financing
documents for Beacon Point. Exact bytes were uploaded, downloaded, and
hash-matched before sealing. No claim, entity, capacity fact, or public source
copy is created by the capture.

## Verify

```bash
python3 -m engine.archive.capture verify-batch \
  --root . \
  --manifest research/m3/evidence-captures/2026-07-25/manifest.json \
  --expected-receipts 1

python3 -m engine.archive.capture verify-batch \
  --root . \
  --manifest research/m3/evidence-captures/2026-07-25/manifest-02.json \
  --expected-receipts 1

python3 -m engine.archive.capture verify-batch \
  --root . \
  --manifest research/m3/evidence-captures/2026-07-25/manifest-03.json \
  --expected-receipts 1
```
