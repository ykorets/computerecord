# The Compute Record — target architecture v0.1

**Status:** Proposed foundation
**Date:** 2026-07-13
**Owner:** Yaro Korets

## 1. Purpose

The Compute Record is an evidence-backed system of record for data-center
buildout. It tracks physical campuses from early announcements through land,
permits, utility service, construction, energization, hardware installation,
and operation.

The product is designed around one rule:

```text
Source -> Archive -> Claim -> Review -> Published fact -> Snapshot -> Website
```

The database is authoritative. Websites, APIs, maps, newsletters, counters,
and research are projections of published database facts. No factual value is
maintained by hand in a page component.

## 2. Product boundary

The Compute Record and Behind the Watt are sibling products by Yaro Korets.

| Product | Primary question | Primary entities |
|---|---|---|
| The Compute Record | What data-center capacity is actually moving from plan to operation? | campuses, phases, buildings, tenants, utilities, IT capacity, construction, capital |
| Behind the Watt | What power is actually serving compute behind the meter? | power facilities, permits, equipment, fuel, gas flow, operating evidence |

They share the evidence platform but have separate brands, domains, public
snapshots, site navigation, metrics, and editorial products. Neither product
is presented as an endorsement by the other. Both are attributed to
**Yaro Korets**.

## 3. Requirements

### Functional

1. Discover source changes continuously according to a per-source schedule.
2. Preserve every fetched source immutably before extraction.
3. Extract claims with page-, quote-, cell-, figure-, or observation-level
   anchors.
4. Resolve organizations, sites, campuses, phases, buildings, and power
   assets without losing aliases or merge history.
5. Store typed, temporal, versioned facts with claim-level support.
6. Separate detection, source assertion, corroboration, and verification.
7. Review material changes through an immutable GitHub review manifest.
8. Promote reviewed rows in one idempotent database transaction.
9. Generate independent public snapshots for Compute Record and BTW.
10. Serve the same snapshot through site, files, API, MCP, feeds, and alerts.

### Non-functional

- One human operator with AI assistance.
- Replayable from preserved source documents.
- Publication fails closed; stale publication remains available.
- Public data remains accessible when the operational database is down.
- Median Tier-1 source-to-candidate latency below 15 minutes.
- 95% of reviewed events published within 24 hours of discovery.
- Every published non-derived fact has at least one compatible validated
  claim; every derived fact records its formula and input fact IDs.
- Initial operating cost should remain comfortably below the cost of a
  conventional always-on application stack.

## 4. System context

```text
Primary sources
    |
    v
Source watchers ----> source health / coverage / latency metrics
    |
    v
Candidates -> Fetcher -> Immutable R2 archive -> Extractors
                                                |
                                                v
                                      Validated claim ledger
                                                |
                              normalize / resolve / corroborate
                                                |
                                                v
                                  Typed temporal fact ledger
                                                |
                                       review manifest + PR
                                                |
                                         atomic promotion
                                                |
                  +-----------------------------+----------------------+
                  |                             |                      |
                  v                             v                      v
          Compute snapshot                BTW snapshot        change/outbox feed
                  |                             |                      |
          Astro/API/MCP                 Astro/API/MCP       newsletter/webhooks
```

## 5. Source acquisition

### 5.1 Source registry

Every watched source has an explicit contract:

```text
source
  id
  publisher_id
  jurisdiction
  source_type
  url
  adapter
  schedule
  tier
  expected_change_interval
  maximum_staleness
  coverage_scope
  last_checked_at
  last_success_at
  last_changed_at
  consecutive_failures
```

Source tiers:

- **Tier 1, 5–15 minutes:** SEC filings, corporate IR, structured permit
  feeds, utility feeds, RSS, high-value known dockets.
- **Tier 2, hourly:** state permits, utility commissions, county agendas,
  zoning, construction portals, tax incentives.
- **Tier 3, daily or source cadence:** WAF-heavy registries, satellite
  catalogs, courts, EIA/EPA/FERC safety nets, broad news discovery.

News and competitor pages may create candidates, but cannot directly create
verified facts. A competitor inventory is a coverage benchmark, not an
authoritative import.

### 5.2 Candidate work queue

Postgres `candidate` is the initial durable queue. Workers claim rows with
transactional locking and record attempts. Delivery is at-least-once;
business effects are idempotent through stable external IDs, URLs, and
content hashes.

```text
candidate
  source_id
  external_id
  discovered_at
  source_published_at
  url
  title
  match_reason
  priority
  state: discovered | fetched | extracted | staged | ignored | failed
  attempt_count
  next_attempt_at
```

An external queue is not required at initial scale. Revisit Cloudflare Queues
only after sustained volume above 10,000 candidates/day or when sub-minute
dispatch becomes a product requirement.

## 6. Fetching and evidence archive

The fetcher follows redirects, records response metadata, hashes the payload,
and stores the original object before downstream processing.

```text
r2://evidence-private/docs/{sha256}.{extension}
```

`document` metadata includes:

```text
id, source_id, publisher_id, original_url, final_url,
sha256, r2_key, mime_type, byte_size, pages,
published_at, captured_at, fetched_at,
doc_genre, ocr_quality, language,
rights_basis, redistribution_status, supersedes_document_id
```

The original publisher URL always remains visible as `Source`. A public copy
is exposed only when a rights allowlist permits redistribution. Private and
public R2 buckets are separate.

Satellite scenes use the same document lineage and additionally record
provider, acquisition time, resolution, cloud cover, geometry, and license.
Licensed scenes may remain private while permitted derived observations are
published.

## 7. Extraction and claim validation

Extraction produces immutable source assertions, not canonical facts.

```text
claim
  id
  document_id
  subject_hint
  predicate
  value_text / value_num / value_date / value_json
  unit
  qualifier: exact | approximate | at_least | at_most | range
  anchor_kind: quote | cell | figure | observation
  quote
  page
  bbox
  match_score
  numeric_check
  confidence
  extractor_version
  status: extracted | validated | rejected | superseded
```

Validation requires:

1. Anchor verification against the archived object.
2. Independent numeric relocation for numeric claims.
3. Unit normalization and compatibility.
4. Predicate compatibility.
5. A second pass or human review when OCR is weak or models disagree.

`validated` means the document supports the extraction. It does not mean the
source assertion is true.

## 8. Canonical identity graph

All canonical subjects receive stable UUIDs from a common `entity` table.
Typed subtype tables keep relational integrity without an unbounded EAV
model.

```text
entity(id, entity_type, canonical_name, created_at)

organization(entity_id, organization_type, website, jurisdiction)
place(entity_id, address, county, state, country, geometry, geo_precision)
campus(entity_id, place_id, canonical_slug)
campus_phase(entity_id, campus_id, phase_name)
building(entity_id, phase_id, building_name)
power_asset(entity_id, campus_id, asset_type)
equipment_cohort(entity_id, power_asset_id)
permit(entity_id, authority, permit_no, permit_type)
```

Aliases are first-class and source-supported. Resolver decisions are
versioned, reversible, and reviewed. Deterministic identifiers are preferred:
permit number, parcel ID, legal entity, address, utility account, docket, and
coordinates. LLM matching can propose a merge but cannot publish it.

## 9. Typed temporal fact ledger

The platform uses a common immutable version envelope plus typed fact tables.
This avoids both duplicated history logic and a weak generic key/value store.

```text
fact_version
  id
  subject_entity_id
  fact_kind
  valid_from
  valid_to
  recorded_at
  verification_state
  publication_state
  supersedes_fact_id
  review_id

capacity_fact(fact_id, capacity_type, value_mw, lower_mw, upper_mw,
              qualifier, scope_entity_id, basis)
status_fact(fact_id, status_axis, status_value)
relationship_fact(fact_id, object_entity_id, relationship_type, role)
milestone_fact(fact_id, milestone_type, milestone_date, date_precision)
equipment_fact(fact_id, oem, model, unit_count, mw_each, total_mw, basis)
observation_fact(fact_id, observation_type, observed_at, value, geometry)
```

Evidence uses real foreign keys:

```text
fact_support
  fact_id -> fact_version
  claim_id -> claim
  support_kind: direct | derived
  derivation
  input_fact_ids[]
```

Verification states are distinct from publication state:

- `source_asserted`
- `corroborated`
- `verified`
- `disputed`

Publication states:

- `candidate`
- `staging`
- `published`
- `retracted`

## 10. Capacity semantics

Capacity types are never coalesced through fallback logic and are never added
across incompatible scopes.

- `utility_service_mw`
- `gross_generation_nameplate_mw`
- `permitted_generation_mw`
- `critical_it_mw`
- `contracted_it_mw`
- `energized_it_mw`
- `occupied_it_mw`
- `planned_it_mw`

Every capacity value records:

- campus, phase, building, or asset scope;
- gross/critical/IT/generation basis;
- exact, approximate, lower bound, upper bound, or range qualifier;
- source and validity dates;
- verification state;
- supporting claim IDs.

Aggregates declare their accepted capacity type and input fact IDs. Missing is
`null`, never zero.

## 11. Multidimensional project status

A single `planned/building/live` field is insufficient. Status is modeled as
parallel axes:

| Axis | Example progression |
|---|---|
| Site control | rumored -> optioned -> acquired |
| Zoning | not_filed -> filed -> approved -> appealed |
| Environmental | not_filed -> filed -> draft -> issued -> challenged |
| Utility | requested -> study -> contracted -> energized |
| Construction | clearing -> shell -> MEP -> commissioned |
| Compute | ordered -> delivered -> installed -> serving |
| Commercial | marketed -> tenant_reported -> contracted |
| Finance | announced -> committed -> closed |

A human-friendly summary stage is a derived projection. The underlying axes
remain available in dossiers and API responses.

## 12. Review and atomic promotion

1. Normalization creates new staged fact versions.
2. The truth gate validates compatible evidence and typed values.
3. A review is sealed as exact row IDs plus a SHA-256 manifest hash.
4. A GitHub PR shows old value, proposed value, evidence anchor, source URL,
   derivation, and entity-resolution decisions.
5. Merge is the human publication decision.
6. One idempotent database transaction verifies the manifest, retracts prior
   logical versions, publishes only approved versions, recomputes projections,
   stores the merge commit, and writes a publication outbox event.

Promotion never scans and publishes "whatever is staging." Code PRs and data
review PRs remain separate workflows.

## 13. Storage boundaries

Initial deployment uses one Supabase Postgres project with separated schemas
and roles:

```text
core      source, document, claim, entity, fact, review
compute   campus projections and Compute Record aggregates
btw       power projections and BTW aggregates
ops       pipeline runs, attempts, SLOs, publication outbox
```

Benefits: one identity graph, shared documents, real cross-product joins, and
low operational cost. The schemas are the boundary; the database is not
publicly queryable.

The existing BTW schema is migrated incrementally. It is not renamed or moved
in the first Compute Record migration. Compatibility views allow the current
publisher to continue working while shared core tables are introduced.

Large time series and raster-derived data live as Parquet/COG objects on R2.
Postgres stores metadata, summaries, and lineage, not every raster pixel.

## 14. Publication and public data plane

Postgres is operational truth; generated snapshots are public truth. Each
promotion creates content-addressed files and a manifest:

```text
manifest.json
campuses.json
organizations.json
relationships.json
capacities.json
events.json
changes.jsonl
coverage.json
campuses.geojson
snapshot.parquet
```

The manifest contains schema version, generated timestamp, input review ID,
file hashes, license, and citation. Compute Record and BTW receive different
projections from the same published fact ledger.

Snapshots are committed to generated mirror branches for public diff history.
They are never edited by hand.

## 15. Product delivery

### Websites

Astro builds crawlable static pages from the generated snapshot:

- home dashboard;
- map and data explorer;
- campus and phase dossiers;
- chronological change feed;
- state and regulator coverage;
- organization/vendor/tenant graph;
- methodology and source freshness.

Client JavaScript powers maps, filters, and image comparison only. Every
indexable fact and receipt remains in generated HTML.

### API and agents

- Stable JSON, JSONL, CSV, GeoJSON, and Parquet files.
- OpenAPI facade for filtered queries when file-only access is insufficient.
- Read-only MCP tools over the published snapshot.
- RSS/Atom for public change feeds.
- Signed webhooks for alert subscribers.

Neither API nor MCP reads staging rows or operational Postgres directly.

### Editorial delivery

Published events generate a draft newsletter. A human reviews and sends it.
Subscriptions and PII stay in the Cloudflare Worker/Resend system, outside the
research database.

## 16. Freshness model

The product exposes the complete latency chain:

```text
source_published_at
discovered_at
fetched_at
extracted_at
reviewed_at
published_at
```

Three public record classes allow speed without pretending uncertainty away:

1. **Detected:** a new source document exists; contents not yet reviewed.
2. **Source asserted:** a validated source claim has been extracted.
3. **Verified:** the fact has passed the applicable corroboration rule.

Targets:

- Tier-1 median discovery latency below 15 minutes.
- Tier-2 median discovery latency below 2 hours.
- Source-to-reviewed publication below 4 hours for priority changes.
- 95th percentile reviewed publication below 24 hours.

## 17. Reliability and failure behavior

- Every stage is idempotent and retryable.
- Document SHA-256 deduplicates repeated URLs and mirrors.
- Adapter fixtures detect registry redesigns in CI.
- Source staleness breaches alert even when a registry appears merely quiet.
- Promotion fails closed; the prior public snapshot stays online.
- Archive plus extractor version plus review manifest can reproduce a release.
- Dead-man checks cover scheduler silence.
- A failed source cannot block unrelated sources, but is visible in coverage.
- Corrections create new versions; published history is never silently edited.

## 18. Security, rights, and privacy

- Operational tables are private and protected by RLS and scoped roles.
- Service credentials live only in GitHub and Cloudflare secrets.
- Public applications receive generated files, never database credentials.
- Evidence publication is rights-allowlisted and fail-closed.
- Licensed satellite scenes remain private unless redistribution is permitted.
- Newsletter addresses are never stored in the research database.
- Every promotion records review ID and Git merge commit.
- Database migrations run against ephemeral PostgreSQL in GitHub Actions before
  production application; no Supabase branch is required.

## 19. Observability

Internal metrics:

- source check and change rates;
- candidate volume and failure rate;
- latency at every pipeline stage;
- document fetch and OCR failures;
- claim validation/rejection and model disagreement;
- human correction rate;
- entity merge/split rate;
- publication duration;
- LLM and infrastructure cost per document and published fact.

Public metrics:

- source coverage and last successful check;
- data `as_of` timestamp;
- latest promotion;
- coverage by state and evidence class;
- percentage of facts source-asserted, corroborated, verified, and disputed.

## 20. Code ownership and migration from BTW

The existing BTW engine remains operational while the shared platform is
extracted. No code is copied into Compute Record as an independent fork.

Migration sequence:

1. Define shared contracts and compatibility tests in this repository.
2. Add Compute Record domain migrations and adapters without changing BTW
   output semantics.
3. Extract reusable watcher/archive/claim/review code into a neutral
   `record_engine` package.
4. Pin both products to the same package version.
5. Move shared CI workflows only after both products pass replay tests.

This is a strangler migration, not a rewrite.

## 21. Target repository structure

```text
computerecord/
  README.md
  docs/
    architecture.md
    roadmap.md
    adr/
  schema/
    migrations/
    regression/
  engine/
    adapters/
    src/record_engine/
    tests/
    evals/
  apps/
    compute-web/
  services/
    public-api/
    mcp/
    source-scheduler/
    newsletter/
  packages/
    data-contracts/
    design-tokens/
  infra/
    cloudflare/
    github/
```

Only directories needed by the current milestone should be created. Empty
architecture theater is avoided.

## 22. Explicit non-goals for the foundation

- No factual website before a generated Compute snapshot exists.
- No direct import of competitor facts as canonical data.
- No public write API.
- No user accounts for the open dataset.
- No Kafka, Kubernetes, or general workflow orchestrator.
- No vector database until a measured search problem requires one.
- No fake 3D campus geometry presented as observation.
- No combining gross generation, utility service, or critical IT capacity.

## 23. Revisit triggers

- Add an external queue above 10,000 candidates/day or sub-minute dispatch.
- Split databases when independent teams or blast-radius requirements outweigh
  cross-product joins.
- Add a dedicated search engine when Postgres full-text/trigram queries fail a
  measured latency target.
- Add authenticated query products when a paying consumer needs saved views,
  quotas, or contractual API SLOs.
- Add streaming only when event volume makes snapshot/diff delivery visibly
  insufficient.

