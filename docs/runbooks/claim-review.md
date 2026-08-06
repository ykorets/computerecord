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

## Record the merge decision

After GitHub merges the proposed packet, author a decision specification with
the exact approved head commit, merge commit, merge timestamp, reviewer
identity, approved candidate IDs, and blocked claim IDs. Build the immutable
decision:

```bash
python3 -m engine.research.decision build \
  --spec "$PACKET_DIR/decision-spec.json" \
  --review-manifest "$PACKET_DIR/review-manifest.json" \
  --entity-seeds "$PACKET_DIR/entity-seeds.json" \
  --output "$PACKET_DIR/review-decision.json"
```

The verifier requires the complete entity-candidate set and preserves every
blocked normalization. The decision permits only a future staging
transaction: it cannot create facts, promote data, or write to the database.

## Typed fact-normalization review

Do not add typed facts to an already merged claim-review packet. Those packets
and their GitHub decisions are immutable. Create a second review-only packet
that pins the validated claims and entity seeds by SHA-256:

```bash
python3 -m engine.research.normalizations build \
  --spec "$NORMALIZATION_DIR/spec.json" \
  --claims "$CLAIM_PACKET/claims.json" \
  --entity-seeds "$CLAIM_PACKET/entity-seeds.json" \
  --output-dir "$NORMALIZATION_DIR"
```

Every candidate explicitly declares `epistemic_type`, `verification_state`,
period, issue vintage, forecast horizon, scenario, exact support claims, and a
typed payload. Version 1 accepts capacity payloads and rejects incompatible
capacity type/basis pairs or MW values absent from the supporting claims.
Forecasts require a UTC `issued_at` and a horizon; non-forecasts cannot carry
forecast-only fields.

```bash
python3 -m engine.research.normalizations verify \
  --packet-dir "$NORMALIZATION_DIR" \
  --spec "$NORMALIZATION_DIR/spec.json" \
  --claims "$CLAIM_PACKET/claims.json" \
  --entity-seeds "$CLAIM_PACKET/entity-seeds.json"
```

The generated `fact-normalizations.json` and
`normalization-review-manifest.json` remain staging candidates only. They
cannot write database rows, create facts, or authorize promotion.

## Seal an identity-staging plan

After one or more immutable review decisions approve entity seeds, combine
them with `engine.research.staging`. The builder re-verifies the complete hash
chain from validated claims through GitHub decisions, requires exact candidate
sets and support claims, resolves only within-batch dependencies, and reports
canonical-schema blockers without filling them in.

The resulting plan remains review-only: its policy forbids database writes,
facts, canonical rows, and promotion. CI must reproduce it byte-for-byte before
a separate data-review transaction can be proposed.
