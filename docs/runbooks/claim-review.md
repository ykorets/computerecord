# Anchored claim review runbook

This stage converts a captured document into validated source assertions and
proposed entity seeds. It does not create canonical facts.

## Author the specification

Each specification declares:

- the exact source SHA-256;
- short quote or structured XBRL anchors;
- typed source values and predicates;
- entity candidates and their supporting claim keys;
- any fact normalizations that must remain blocked.

Quotes must occur exactly once in normalized document text. XBRL facts must
match one exact concept/value pair. Text and numeric claim values must appear
in their declared anchors.

## Build from private archive bytes

```bash
python3 -m engine.research.claims build \
  --spec "$SPEC_PATH" \
  --receipt "$RECEIPT_PATH" \
  --object-file "$DOWNLOADED_R2_OBJECT" \
  --output-dir "$PACKET_DIR"
```

The builder first verifies the raw object against the capture receipt. It then
creates stable claim and entity-candidate IDs from the source hash and logical
keys.

## Verify

Before review, verify against the archive bytes:

```bash
python3 -m engine.research.claims verify \
  --packet-dir "$PACKET_DIR" \
  --spec "$SPEC_PATH" \
  --receipt "$RECEIPT_PATH" \
  --object-file "$DOWNLOADED_R2_OBJECT"
```

CI performs repository-only verification of exact input/output hashes,
support links, classifications, and fail-closed policy. CI deliberately does
not fetch the publisher URL; the immutable archive is the downstream source.

## Review boundary

- `validated_source_assertions` means the source contains the assertion.
- `staging_entity_seed_candidates` means no entity row exists yet.
- ambiguous capacity, status, or relationship semantics stay blocked.
- merging the proposal requests a review decision.
- a separate decision artifact records the merge commit.
- promotion remains a later idempotent database transaction.
