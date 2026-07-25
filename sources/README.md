# Primary-source registry

This directory contains the sealed operational contracts for sources watched
by the Compute Record engine. It is public configuration, not factual output.

The first registry cohort contains ten official SEC submissions endpoints for
public operators represented in the P0 research queue. The SEC documents that
the submissions API as a real-time public filing history endpoint. The
registry pins the official company/CIK index used to resolve watcher identity.

Every watcher is Tier 1:

- poll interval: 10 minutes, with up to 60 seconds of jitter;
- maximum staleness: 15 minutes;
- adapter: `sec_submissions_v1`;
- output: filing discovery candidates only.

A discovery candidate cannot create a fact. The referenced filing document
must still be captured into the private content-addressed archive, anchored,
reviewed, and promoted through the ordinary truth path.

Runtime timestamps and failures do not belong in this sealed file. Watcher
observations and health are a separate append-only operational artifact.

`schedule.json` is generated from the registry. It evenly phases sources in
each interval cohort, pins the registry hash, prevents concurrent runs for one
source, and preserves the 15-minute freshness deadline. CI rebuilds it
byte-for-byte.

The first append-only observation batch performs real reads of all registered
SEC endpoints. It commits response hashes, sizes, status, and validated CIKs,
but never raw API responses. `health/` is a deterministic projection that
distinguishes a successful unchanged source (`source_silent_healthy`) from a
failed watcher (`watcher_failed`) and an overdue watcher (`stale`).

The `sec_submissions_v1` adapter converts the SEC's columnar recent-filings
response into stable accession-based candidates. Recorded fixtures cover
irrelevant-form filtering, amendments, cursor advancement, official archive
URL construction, and fail-closed behavior when a cursor disappears. A
candidate remains `detected`; its filing document must still pass capture and
review.

Verify:

```bash
python3 -m engine.sources.registry verify \
  --registry sources/registry.json \
  --expected-sources 10

python3 -m engine.sources.schedule verify \
  --registry sources/registry.json \
  --schedule sources/schedule.json
```
