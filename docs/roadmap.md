# Compute Record Data Foundation roadmap

**Owner:** Yaro Korets
**Principle:** database and evidence first; the website follows the public
snapshot.

## M0 — Project foundation

Deliverables:

- project charter and brand identity;
- target architecture;
- accepted shared-platform ADR;
- repository and CI skeleton;
- explicit product/data non-goals.

Definition of done:

- every implementation decision can be checked against a written data path;
- `computerecord.com` is reserved;
- no production site is created prematurely.

## M1 — Shared truth baseline

**Status: CLOSED 2026-07-14.** The sealed review, atomic promotion, generated
mirror, site rebuild, and replay-safe no-op are recorded in
[`docs/baselines/btw-mirror-v1.md`](baselines/btw-mirror-v1.md). CI pins that
baseline and verifies the live BTW mirror against its v1 contract.

Before adding a new domain, finish the open BTW truth-integrity work that the
shared platform depends on.

Deliverables:

- migration 008 regression-tested in ephemeral PostgreSQL through GitHub CI;
- read-only production audit;
- all current unit/permit violations represented as review items;
- atomic, manifest-bound promotion proven end to end;
- compatibility snapshot for existing BTW public output.

Definition of done:

- no direct database patching;
- unsupported facts cannot be published;
- Compute work cannot regress the BTW mirror.

## M2 — Compute domain schema

**Status: IMPLEMENTED; PRODUCTION DEPLOYMENT PENDING.** The migration and its
regression scenarios are merged. A manual, checksum-bound GitHub deployment
workflow is also merged and restricted to `main`. Production application
waits for the Supabase access token and database password in the protected
GitHub environment.

Deliverables:

- base entity and alias model;
- organizations, places, campuses, phases, buildings, power assets;
- typed temporal fact envelope;
- capacity, status, relationship, milestone, equipment, and observation facts;
- real FK-based fact support;
- capacity and status vocabularies;
- migrations and SQL regression scenarios.

Definition of done:

- incompatible capacity types cannot be aggregated accidentally;
- unknown is represented as `NULL`;
- a fact can be corrected without deleting history;
- every published fact version can enumerate its evidence.

## M3 — Coverage benchmark and entity seeds

**Status: IN PROGRESS.** The 2026-07-14 capture contains 50 explicit
`benchmark_only` targets, hashes of both source responses, one deterministic
BTW identity match, 49 unresolved targets, and reproducible gap reports. A
sealed intake queue now schedules all 49 unresolved targets while keeping 195
competitor-provided links explicitly unverified. The first independently
discovered Childress SEC filing is now content-addressed in the shared private
archive and sealed by a remote-byte-verified receipt. It remains document-only:
no database write or publication occurred. A reviewed packet binds
six exact anchored source assertions to three Childress entity-seed candidates.
PR #6 approved those candidates only for a future staging transaction, and an
immutable decision pins the reviewed head, merge commit, reviewer, and packet.
The filing's reported 750 MW is retained as a source assertion but blocked from
fact normalization because its capacity type and service scope are ambiguous.
A generated progress ledger now overlays immutable receipts and decisions on
the sealed 49-task queue. A second independently rediscovered SEC document now
preserves the complete Delta Forge 1 submission in private R2. Its six source
assertions and three entity seeds passed GitHub review. An immutable decision
approves only the identity seeds for future staging; capacity and
construction-status normalizations remain blocked pending typed scope
evidence. Current progress: two captured and reviewed tasks, six approved
identity candidates, three blocked normalizations, and zero facts. A third
independently discovered complete SEC submission now preserves Hut 8's Beacon
Point filing in private R2. Eight anchored source assertions and four entity
seeds are proposed. Its 352 MW measure is explicitly reported as combined
critical IT capacity across six data halls and is eligible for later typed
normalization; this packet still creates no fact.

Deliverables:

- snapshot of the competitor's 50 public campus targets with capture time,
  public URL, and content hash;
- explicit `benchmark_only` classification;
- comparison against existing BTW facilities and announcements;
- deterministic entity-resolution candidates;
- coverage gap report by campus, state, source class, and missing field.

Definition of done:

- no competitor value is treated as canonical without an independent source;
- every target is resolved, marked unresolved, or intentionally out of scope;
- direct overlaps with BTW share identity rather than duplicate records.

## M4 — Primary-source registry

**Status: IN PROGRESS.** The first sealed cohort defines ten Tier-1 SEC
submissions watchers for public operators in the P0 queue. It pins official
CIK identity, schedule, adapter, coverage, and a 15-minute staleness SLO while
remaining discovery-only. A generated scheduler plan spreads the ten watchers
across their polling window with no phase collisions and pins the registry
hash. Append-only observation batches now retain response hashes rather than
raw API payloads, and a generated health projection distinguishes source
silence, watcher failure, and staleness. A recorded SEC adapter now produces
stable accession-based filing candidates while filtering irrelevant forms and
requiring document capture. Non-SEC sources are next.

Deliverables:

- source inventory for SEC, company IR, permits, utility commissions,
  planning/zoning, tax incentives, construction, interconnection, and courts;
- tier, schedule, coverage scope, and staleness SLO for every source;
- first fast Tier-1 watchers;
- recorded adapter fixtures and health reporting.

Definition of done:

- source silence is distinguishable from watcher failure;
- discovery latency is measured rather than guessed;
- coverage is publishable as data.

## M5 — Archive, claims, and first dossiers in the database

Deliverables:

- immutable R2 capture for independently sourced documents;
- rights and redistribution metadata;
- anchored claim extraction and validation;
- entity resolution and staged fact creation;
- GitHub review manifest and atomic promotion;
- first independently supported campus, organization, capacity, relationship,
  and milestone records.

Definition of done:

- each promoted value traces to a preserved source anchor;
- source assertions and verified facts are visibly different;
- replaying the archived documents produces the same reviewed candidates.

## M6 — Compute public snapshot

Deliverables:

- versioned snapshot manifest;
- campuses, organizations, relationships, capacities, events, changes,
  coverage, and GeoJSON exports;
- hashes, citation, license, schema version, and `as_of` timestamps;
- generated mirror branch;
- contract and consistency tests.

Definition of done:

- a third party can reconstruct the current public dataset without the site;
- no snapshot field comes from hand-maintained frontend content;
- old snapshots remain addressable and diffable.

## M7 — Alpha product

Only now build the public application.

Deliverables:

- Astro site generated from the Compute snapshot;
- campus dossier pages with evidence receipts;
- map and table explorer;
- change feed;
- source coverage and freshness dashboard;
- methodology and data download pages;
- canonical domain deployment at `computerecord.com`.

Definition of done:

- deleting the local frontend cache and rebuilding from the snapshot produces
  the same factual site;
- every visible count is computed from published data;
- missing fields render as unknown, not zero;
- pages remain crawlable without client JavaScript.

## M8 — Agent and alert distribution

Deliverables:

- OpenAPI query facade over the public snapshot;
- MCP tools for campuses, changes, evidence, capacity, and source freshness;
- RSS/Atom change feeds;
- signed webhook delivery;
- separate Compute Record Resend segment and editorial workflow.

Definition of done:

- agents never need to scrape visual pages;
- API/MCP responses use the same snapshot as the site;
- alerts identify detection, assertion, and verification state.

## Product-level launch gates

The public alpha should not be described as comprehensive until:

1. All 50 benchmark campuses have an explicit resolution state.
2. Every displayed capacity has a declared capacity type and scope.
3. Every displayed status comes from a typed status axis or a documented
   derived projection.
4. Every published fact has compatible support.
5. Freshness metrics are generated from real pipeline timestamps.
6. The site contains no hand-maintained factual data.
