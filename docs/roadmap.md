# The Compute Record — implementation roadmap

**Version:** 0.2

**Updated:** 2026-08-05

**Owner:** Yaro Korets

**Principle:** database and evidence first; every interface is a projection of
the published snapshot.

## Current position

The foundation is real, but the product does not yet contain a canonical
Compute fact or public Compute snapshot. Work completed ahead of milestone
order is recorded as partial implementation, not as a closed milestone.

| Milestone | State | What is true now |
|---|---|---|
| M0 Foundation | Closed | Repository, domain, architecture, CI, brand, and product boundary exist. |
| M1 Shared truth baseline | Closed | GitHub review manifest, atomic promotion, replay-safe mirror, and BTW compatibility baseline are proven. |
| M2 Core Compute schema | Implemented; deployment pending | Typed entities/facts and SQL regression tests are merged; production credentials and deployment are pending. |
| M2.1 Measurement semantics | Implemented; deployment pending | Additive schema, truth gates, and regression scenarios exist; review, merge, and production deployment are pending. |
| M3 Coverage and identity | In progress | 50-target benchmark, 49-task independent intake queue, three private SEC captures, three immutable review decisions, and ten approved identity candidates exist. |
| M4 Source operations | In progress | Ten SEC watchers, deterministic schedule, recorded observations/health, and SEC discovery adapter exist; non-SEC source classes and continuous deployment remain. |
| M5 First published dossiers | Partially implemented | Archive, anchored-claim, review-packet, and decision tooling exist; no database rows or canonical facts have been written. |
| M6 Public snapshot | Not started | No Compute snapshot or generated mirror exists. |
| M7 Campus alpha | Not started | No Compute Record website exists. |
| M8 Market intelligence | Not started | No market dossiers, reproducible funnels, comparison pages, or infrastructure atlas exist. |
| M9 Agent and alert distribution | Not started | No Compute API, MCP, feeds, webhooks, or newsletter segment exists. |

The generated ledger at `research/m3/progress.json` is the canonical detailed
record of research progress. This roadmap records product-level status.

## Product invariants

1. `Source -> Archive -> Claim -> Review -> Published fact -> Snapshot -> Interface`.
2. No competitor value becomes canonical without independent evidence.
3. Verification state and measurement mode are separate dimensions.
4. Forecast, modeled, estimated, and observed values never silently enter
   current/actual totals.
5. Capacity types and scopes are never combined through fallback logic.
6. Missing means `NULL`, never zero.
7. Every aggregate declares its definition, coverage, vintage, and input facts.
8. Satellite imagery creates observations, not inferred capacity.
9. The website, API, MCP, feeds, maps, and newsletter use the same snapshot.
10. This roadmap changes Compute Record only; it does not authorize BTW product
    or data changes.

## M0 — Project foundation

**Status: CLOSED.**

Completed:

- project charter, public identity, and `computerecord.com`;
- target architecture and explicit product boundary;
- repository and CI skeleton;
- ADR-001 shared evidence platform;
- database-first product rule and non-goals.

## M1 — Shared truth baseline

**Status: CLOSED 2026-07-14.**

Completed:

- migration 008 regression-tested in ephemeral PostgreSQL;
- read-only production audit and reviewed repair path;
- immutable review manifest and atomic promotion;
- generated mirror and replay-safe no-op;
- pinned BTW compatibility contract.

The baseline is now a dependency contract. Compute work must not require new
BTW product changes.

## M2 — Core Compute domain schema

**Status: IMPLEMENTED; PRODUCTION DEPLOYMENT PENDING.**

Completed:

- entity and alias graph;
- organizations, places, campuses, phases, buildings, and power assets;
- immutable temporal fact envelope;
- capacity, status, relationship, milestone, equipment, and observation facts;
- FK-backed evidence support and derived-input lineage;
- capacity and multidimensional status vocabularies;
- SQL regression scenarios;
- checksum-bound GitHub production deployment workflow.

Remaining:

- configure protected GitHub deployment credentials;
- add M2.1 semantics before first production Compute facts;
- run the checksum-bound migration through GitHub;
- record deployment receipt and post-deploy read-only audit.

## M2.1 — Measurement, forecast, metric, and infrastructure semantics

**Status: IMPLEMENTED; PRODUCTION DEPLOYMENT PENDING.** Architectural decision is recorded in
[`ADR-002`](adr/ADR-002-measurement-and-market-semantics.md).

Implemented:

- `epistemic_type`: observed, administrative, reported, estimated, modeled,
  forecast, and derived;
- issue date, period, forecast horizon, optional scenario, and release vintage;
- metric definition registry with formula, accepted fact kinds/capacity types,
  geography, unit, methodology version, and aggregation rules;
- metric observations with coverage, uncertainty, input fact IDs, and snapshot
  lineage;
- typed market/submarket and infrastructure nodes for utility, grid,
  transmission, water, fuel, fiber, and cable dependencies;
- satellite observation metadata and fail-closed inference rules;
- additive migration and regression tests proving the semantic truth gates.

Remaining:

- extend normalization and review packets with epistemic semantics;
- draft the snapshot contract for metrics, markets, infrastructure, and
  satellite observations;
- merge the reviewed migration and deploy M2 + M2.1 through the guarded GitHub
  workflow.

Definition of done:

- a verified forecast cannot enter an actual-capacity aggregate;
- every public time-series point identifies method, period, vintage, and
  inputs;
- an infrastructure or satellite map feature cannot be hand-authored in the
  frontend;
- the existing M2 contract remains backward compatible.

## M3 — Coverage benchmark and canonical identity seeds

**Status: IN PROGRESS.**

Implemented:

- sealed 50-campus competitor benchmark classified `benchmark_only`;
- one deterministic BTW identity match and 49 unresolved targets;
- sealed 49-task independent primary-source intake queue;
- 195 competitor-provided links retained as unverified research cues;
- three complete SEC submissions preserved in private R2 with byte-verified,
  content-addressed receipts: Childress, Delta Forge 1, and Beacon Point;
- anchored packets for all three captures;
- immutable review decisions for Childress, Delta Forge 1, and Beacon Point;
- ten identity candidates approved for future staging;
- three unsafe capacity/status normalizations explicitly blocked;
- Beacon Point's reported 352 MW identified as combined critical IT capacity
  across six data halls and eligible for a separate M2.1 typed normalization
  review;
- generated progress ledger proving zero database writes and zero facts.

Remaining:

- stage approved identity seeds through the ordinary database review path;
- independently source and resolve the remaining queue, P0 before P2;
- record `resolved`, `unresolved with searched sources`, or `out_of_scope` for
  every benchmark target;
- publish gap reporting by campus, geography, operator, source class, and
  missing field.

Definition of done:

- all 50 targets have explicit resolution state;
- every canonical seed has independent support and reversible resolution
  history;
- no benchmark value is treated as a fact.

## M4 — Primary-source operations

**Status: IN PROGRESS.**

Implemented:

- first sealed cohort of ten Tier-1 SEC submissions watchers;
- official CIK identity, 10-minute cadence, and 15-minute staleness SLO;
- deterministic collision-free watcher schedule;
- append-only source observations and deterministic health projection;
- source silence, watcher failure, and staleness are distinguishable;
- recorded SEC discovery adapter with stable accession candidates and
  fail-closed cursor behavior.

Remaining source cohorts:

1. company IR and press-release feeds;
2. planning, zoning, building, and environmental permits;
3. utilities, public-service commissions, interconnection, substations, and
   transmission upgrades;
4. tax incentives, bonds, land records, and economic-development agreements;
5. construction, equipment, tenant, financing, and supply-chain disclosures;
6. courts and administrative appeals;
7. satellite catalogs and licensed-scene policies;
8. water, fuel, fiber, and cable infrastructure sources;
9. market-series sources with explicit definitions and redistribution rights.

Operational deliverables:

- deploy continuous schedules rather than recorded plans only;
- durable candidate queue integration, retries, and dead-letter visibility;
- adapter fixtures and SLOs for every source family;
- public coverage and freshness projection;
- source-to-candidate latency measurements.

Definition of done:

- priority campuses have at least one identity, development, utility, permit,
  and observation path where the jurisdiction exposes one;
- source silence is never reported as current coverage without a health check;
- coverage can be published without exposing private evidence.

## M5 — First canonical facts and campus dossiers in the database

**Status: PARTIALLY IMPLEMENTED; NO FACTS YET.**

Already implemented as filesystem/engine capability:

- private immutable R2 capture with remote-byte verification;
- anchored claim extraction and numeric/source checks;
- sealed review packets and immutable review decisions;
- reproducible research progress projection.

Remaining:

- rights and redistribution metadata in the production document path;
- production entity staging and reversible resolution decisions;
- normalizer updated for M2.1 semantics;
- stage Beacon Point's eligible critical IT capacity without broadening scope;
- stage compatible relationship and milestone facts;
- seal a data-review manifest over exact staged rows;
- run one idempotent atomic promotion;
- replay archive -> claims -> reviewed rows and prove identical output;
- complete at least three independently supported campus dossiers with
  different evidence profiles.

Definition of done:

- each promoted value traces to a preserved anchor;
- source assertion, corroboration, verification, and epistemic type remain
  visible and distinct;
- replay produces the same reviewed candidates;
- correction creates a new fact version rather than rewriting history.

## M6 — Versioned Compute public snapshot

**Status: NOT STARTED.**

Deliverables:

- content-addressed manifest and schema version;
- campuses, phases, buildings, organizations, relationships, capacities,
  statuses, milestones, observations, infrastructure dependencies, metrics,
  evidence receipts, changes, coverage, and freshness exports;
- JSON, JSONL, CSV, GeoJSON, and Parquet distributions where appropriate;
- explicit method, period, vintage, uncertainty, and input IDs for indicators;
- separate actual and forecast datasets/views;
- hashes, citation, license, `as_of`, input review, and release notes;
- generated mirror branch with historical diffs;
- contract, referential-integrity, aggregate, and no-hand-data tests.

Definition of done:

- a third party can reconstruct every public total without the site;
- previous snapshots remain addressable and diffable;
- all site-ready facts and map layers exist in the snapshot;
- public distribution remains available when the operational database is down.

## M7 — Campus-level public alpha

**Status: NOT STARTED. Begins only after M6.**

Deliverables:

- Astro site built only from the Compute snapshot;
- home dashboard with actual, under-construction, contracted, and forecast
  capacity displayed as separate measures;
- campus and phase dossiers;
- multidimensional status and capacity ladder;
- evidence timeline, receipts, missing-evidence panel, and correction history;
- infrastructure dependency graph;
- before/after satellite observations with acquisition date, resolution,
  license, geometry, and stated limitations;
- campus map, data explorer, change feed, methodology, coverage, freshness, and
  data-download pages;
- related-record links where shared identity connects to BTW, with both
  products attributed independently to Yaro Korets;
- canonical deployment at `computerecord.com`.

Definition of done:

- deleting the frontend cache and rebuilding from the snapshot reproduces the
  same factual site;
- every number and map feature is inspectable;
- missing renders as unknown, not zero;
- pages remain crawlable without client JavaScript;
- satellite evidence is never presented as standalone proof of capacity or
  operation.

## M8 — Market intelligence and infrastructure atlas

**Status: NOT STARTED.**

Deliverables:

- typed market and submarket definitions;
- first complete market vertical slice, then repeatable market dossiers;
- delivery funnel: announced -> site controlled -> permitted -> power
  contracted -> construction -> energized -> occupied;
- historical conversion and delivery-velocity series;
- market comparison across compatible metrics;
- grid/utility, transmission, water, fuel, fiber/cable, and satellite layers;
- constraint and policy timelines including moratoria and upgrade dates;
- every market card exposes definition, coverage, vintage, and input campuses;
- saved, content-addressed chart/table datasets for citation.

The first market should be chosen by evidence coverage, not marketing value.
Northern Virginia and Phoenix are candidates only after a coverage audit.

Definition of done:

- no market aggregate depends on frontend logic;
- early-stage and forecast capacity cannot be mistaken for delivered capacity;
- users can open the exact campuses and facts behind every chart segment;
- incomplete research coverage is displayed next to the metric.

## M9 — Agent, alert, and editorial distribution

**Status: NOT STARTED.**

Deliverables:

- OpenAPI query facade over the public snapshot;
- read-only MCP tools for campuses, markets, changes, evidence, capacities,
  infrastructure, metrics, and source freshness;
- RSS/Atom change feeds and signed webhooks;
- notification events that distinguish detected, source-asserted, and
  verified changes;
- separate Compute Record Resend segment and human-reviewed editorial flow;
- machine-readable citation and dataset-discovery metadata.

Definition of done:

- agents never need to scrape visual pages;
- API, MCP, files, feeds, and site return the same snapshot version;
- alerts include evidence state, measurement mode, and correction links;
- no subscriber PII enters the research database.

## Immediate execution sequence

The next ten implementation sprints should be small, reviewable PRs:

1. **Completed:** seal Beacon Point's immutable review decision; no database
   write.
2. **Completed:** implement ADR-002 additive schema migration and SQL regression
   scenarios.
3. Extend claim normalization and review packets with epistemic semantics.
4. Configure and execute the guarded M2 + M2.1 production deployment.
5. Stage approved Childress, Delta Forge, and Beacon Point identities.
6. Stage Beacon Point's scoped 352 MW critical IT fact and compatible
   relationship/milestone facts.
7. Seal and atomically promote the first Compute data-review manifest.
8. Generate Compute snapshot v1 and a content-addressed mirror.
9. Build the first snapshot-only campus dossier as an end-to-end proof.
10. Add the next non-SEC source cohort, prioritizing utility/interconnection
    evidence needed by the first dossiers.

Each sprint ends with tests, generated artifact verification, a focused PR,
and an updated progress projection. Research capture can continue in parallel,
but it cannot bypass these gates.

## Public alpha launch gates

The product must not be described as comprehensive until:

1. all 50 benchmark campuses have explicit resolution state;
2. every displayed capacity declares type, scope, qualifier, and epistemic
   type;
3. every displayed status comes from an axis or documented projection;
4. every published non-derived fact has compatible support;
5. every derived value records formula and exact input facts;
6. actual, forecast, estimated, and modeled values are visibly separated;
7. freshness is generated from real pipeline timestamps;
8. market metrics publish coverage and methodology;
9. satellite observations include limitations and do not infer MW;
10. the site contains no hand-maintained factual data.
