# BTW shared truth baseline

**Status:** closed
**Closed:** 2026-07-14
**Purpose:** immutable compatibility boundary for The Compute Record M2+

The Compute Record begins its domain migrations only after the shared Behind
the Watt truth path was proven end to end without direct database patches.

## Pinned baseline

- BTW merge commit: `ee25bc75da58f167c54055ee1514caabc7c4287f`
- Data review: [ykorets/btw#58](https://github.com/ykorets/btw/pull/58)
- Review ID: `5808b13d-826f-4857-89c2-feebadf6175b`
- Manifest hash: `f674586ce52c54674f71c5875484b9ebe89d4f5eb469229c50c63b431845fab4`
- Generated mirror commit: `d5ccb766ad6630784b9de38837948f87e692d94e`
- Promotion run: [29353822573](https://github.com/ykorets/btw/actions/runs/29353822573)
- Site publication run: [29353839295](https://github.com/ykorets/btw/actions/runs/29353839295)
- Replay-safe dry run: [29353971613](https://github.com/ykorets/btw/actions/runs/29353971613)

## Proven properties

1. Migration 008 passes its immutable-manifest and atomic-promotion regression
   in ephemeral PostgreSQL.
2. Promotion published exactly one unit version and three permit versions from
   the sealed manifest; prior logical versions became `retracted` atomically.
3. A staged unsupported permit (`O4721`) remained staging and was not exported.
4. The generated mirror retained the v1 file contract and rebuilt the Astro
   site successfully.
5. Re-running reconciliation produced `0 new provenance links` and
   `0 staged field updates`.

## Compatibility rule

Compute Record CI checks the current generated BTW mirror with the compatibility
code pinned at this merge commit. Compute migrations are additive in private
`core` and `compute` schemas and may not alter the existing BTW public output.
