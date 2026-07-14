# ADR-001: Build two products on one evidence platform

**Status:** Accepted
**Date:** 2026-07-13
**Decider:** Yaro Korets

## Context

Behind the Watt already operates an evidence pipeline for behind-the-meter
power: source watchers, immutable document capture, anchored extraction,
normalization, human review, atomic publication, public snapshots, Astro,
OpenAPI, and MCP.

The Compute Record has a broader data-center domain: campuses, phases,
buildings, utilities, IT capacity, construction, tenants, capital, and supply
chain. The brands and audiences are related but not identical.

The project must avoid two failure modes:

1. Expanding BTW until power facts and general campus facts lose clear
   semantics.
2. Forking the evidence engine and creating two contradictory archives and
   review systems.

## Decision

The Compute Record and Behind the Watt will be separate sibling products by
**Yaro Korets**, backed by a shared evidence platform.

- The operational database and immutable source archive are shared.
- Core source, document, claim, entity, fact, review, and audit concepts are
  shared.
- Each product owns its domain projections, aggregate definitions, public
  snapshot, site, API surface, MCP tools, methodology, and editorial voice.
- The Compute Record website is built only from its generated public snapshot.
- Existing BTW engine code is extracted incrementally into a neutral package;
  it is not copied into a permanent Compute Record fork.

## Options considered

### Option A: Expand Behind the Watt into the campus registry

| Dimension | Assessment |
|---|---|
| Initial complexity | Low |
| Semantic clarity | Low |
| Brand flexibility | Low |
| Data reuse | High |
| Long-term maintainability | Medium |

**Pros**

- Fastest initial implementation.
- Existing site and distribution already work.

**Cons**

- BTW's power-specific promise becomes unclear.
- Gross generation, utility service, and IT load are too easy to mix.
- Campus users and power users receive an overloaded interface.

### Option B: Build Compute Record as an independent stack

| Dimension | Assessment |
|---|---|
| Initial complexity | Medium |
| Semantic clarity | High |
| Brand flexibility | High |
| Data reuse | Low |
| Long-term maintainability | Low |

**Pros**

- Complete product independence.
- No migration pressure on BTW.

**Cons**

- Duplicate watchers, archives, entities, evidence, and review code.
- The same source can produce conflicting facts in two databases.
- Twice the maintenance burden for one operator.

### Option C: Separate products, shared evidence platform

| Dimension | Assessment |
|---|---|
| Initial complexity | Medium |
| Semantic clarity | High |
| Brand flexibility | High |
| Data reuse | High |
| Long-term maintainability | High |

**Pros**

- One preserved document and one canonical identity graph.
- Independent product semantics and interfaces.
- BTW power evidence enriches Compute Record campus dossiers without copying.
- Compute Record campus entities improve BTW facility resolution.

**Cons**

- Requires explicit schema and role boundaries.
- Shared migrations need compatibility discipline.
- A staged engine extraction is required.

Selected: **Option C**.

## Trade-off analysis

The additional schema and packaging work is justified because provenance and
identity are the system's moat. Duplicating either would be more expensive
than maintaining a shared platform. Separate public projections protect each
brand from the semantic coupling of a single website.

At current scale, one Postgres project and one immutable private archive are
operationally simpler than distributed services. Product schemas, roles,
snapshot manifests, and regression tests provide sufficient isolation. A
future database split remains possible because public products consume
versioned snapshots rather than direct database tables.

## Consequences

- Compute Record starts with schema and ingestion, not a marketing site.
- The public website cannot contain hand-authored factual values.
- A source document is fetched once and may support facts in both products.
- Capacity and status semantics must be defined before broad ingestion.
- Shared engine extraction must preserve BTW behavior through replay tests.
- Product-specific public snapshots become stable contracts.
- Both products use the attribution **by Yaro Korets**.

## Action items

1. [ ] Define the Compute Record entity and typed fact migrations.
2. [ ] Add compatibility tests against the existing BTW published snapshot.
3. [ ] Create a 50-campus competitor coverage benchmark as non-canonical
       targets with capture metadata.
4. [ ] Independently source and resolve the first campus records.
5. [ ] Implement source, archive, extraction, review, and promotion end to end.
6. [ ] Generate the first Compute Record public snapshot.
7. [ ] Start the Astro application only after step 6.

