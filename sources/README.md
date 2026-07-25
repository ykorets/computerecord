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

Verify:

```bash
python3 -m engine.sources.registry verify \
  --registry sources/registry.json \
  --expected-sources 10
```
