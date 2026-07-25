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

## Verify

```bash
python3 -m engine.archive.capture verify-batch \
  --root . \
  --manifest research/m3/evidence-captures/2026-07-25/manifest.json \
  --expected-receipts 1
```
