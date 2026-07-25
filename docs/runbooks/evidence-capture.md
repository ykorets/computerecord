# Evidence capture runbook

This runbook creates a private, content-addressed source capture without
creating claims, entities, or facts.

## Safety contract

- Independently rediscover the official URL. A competitor-provided link is a
  research hint, never evidence.
- Fetch only public HTTPS hosts on the explicit allowlist.
- Archive the exact response bytes under `docs/<sha256>.<ext>`.
- Use the shared private `btw-docs` R2 bucket.
- Download the remote object and match both SHA-256 and byte size before
  sealing a receipt.
- Default rights to `private_only_pending_review`.
- Do not write database rows during M3 capture.

## Capture

```bash
python3 -m engine.archive.capture fetch \
  --url "$OFFICIAL_URL" \
  --allowed-host sec.gov \
  --captured-at "$CAPTURED_AT" \
  --output-dir "$STAGING_DIR"
```

The fetcher rejects:

- HTTP and credential-bearing URLs;
- hosts outside the explicit allowlist;
- redirects outside the allowlist;
- hostnames resolving to non-public IP addresses;
- unsupported content types;
- suspiciously small or oversized responses.

## Private archive

Use the `archive_key` written to `retrieval.json`.

```bash
wrangler r2 object put "btw-docs/$ARCHIVE_KEY" \
  --remote \
  --file "$STAGING_DIR/source.html" \
  --content-type text/html \
  --force

wrangler r2 object get "btw-docs/$ARCHIVE_KEY" \
  --remote \
  --file "$STAGING_DIR/remote-verified.html"
```

Sealing requires the downloaded remote object, not the original local file:

```bash
python3 -m engine.archive.capture seal \
  --retrieval "$STAGING_DIR/retrieval.json" \
  --remote-object "$STAGING_DIR/remote-verified.html" \
  --bucket btw-docs \
  --target-id "$BENCHMARK_TARGET_ID" \
  --task-id "$INTAKE_TASK_ID" \
  --publisher "$PUBLISHER" \
  --source-class "$SOURCE_CLASS" \
  --discovery-method "$DISCOVERY_METHOD" \
  --verified-at "$VERIFIED_AT" \
  --output "$RECEIPT_PATH"
```

## Batch verification

The batch manifest pins the exact intake queue and every receipt:

```bash
python3 -m engine.archive.capture build-batch \
  --root . \
  --queue research/m3/primary-source-intake/queue.json \
  --receipt "$RECEIPT_PATH" \
  --output "$MANIFEST_PATH"

python3 -m engine.archive.capture verify-batch \
  --root . \
  --manifest "$MANIFEST_PATH"
```

Raw private source files never enter the public Git repository. Repository
artifacts contain receipts, hashes, lineage, and rights state only.
