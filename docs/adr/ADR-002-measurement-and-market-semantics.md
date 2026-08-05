# ADR-002: Separate measurement mode, forecasts, and reproducible indicators

**Status:** Accepted
**Date:** 2026-08-05
**Decider:** Yaro Korets

## Context

The M2 schema correctly separates capacity types, status axes, verification
state, publication state, and evidence support. M3 research has now produced
the first independently archived and anchored campus assertions. Before the
first canonical Compute facts are promoted, the model must also distinguish
what kind of knowledge a value represents.

A forecast can be perfectly supported by a source and still not describe
current capacity. A satellite observation can be verified as an observation
without proving energization or MW. A market total can be reproducible while
some of its inputs remain source-asserted. Verification state alone cannot
express these differences.

The product also needs repeatable market pages, delivery funnels, time series,
and infrastructure maps. Those outputs must be database projections rather
than calculations embedded in the website.

## Decision

Add a measurement and market semantics extension before the first Compute
fact promotion.

1. Every fact version receives an `epistemic_type`:
   `observed`, `administrative`, `reported`, `estimated`, `modeled`,
   `forecast`, or `derived`.
2. Forecasts retain their source assertion, forecast horizon, issue date, and
   optional scenario. They never contribute to actual/current aggregates.
3. Repeated indicators use a registered definition and versioned observation:
   formula, accepted fact types, geography, unit, period, release vintage,
   coverage, uncertainty, methodology version, and exact input fact IDs.
4. Markets, utility/grid nodes, water/fuel/fiber assets, and their dependencies
   are first-class typed entities or relationships in the shared identity
   graph. A website-only infrastructure overlay is prohibited.
5. Satellite and other remote observations remain observations. They may
   corroborate construction or equipment presence under an explicit rule but
   cannot infer capacity or operation by themselves.
6. A delivery funnel is a documented derived projection over the parallel
   status axes. It does not replace those axes.
7. Missing values remain `NULL`; incomplete coverage is published alongside
   every market aggregate.

Verification and epistemic type are orthogonal. For example,
`verification_state=verified` plus `epistemic_type=forecast` means that the
source and extraction are verified, not that the forecast has happened.

## Options considered

### Option A: Keep only verification and publication state

| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Migration cost | Low |
| Semantic safety | Low |
| Market analytics | Weak |

**Pros:** no schema extension before the first promotion.

**Cons:** forecasts, estimates, administrative values, and observations can be
mistaken for current reality; market charts need undocumented frontend logic.

### Option B: Extend the fact ledger and add a metric registry

| Dimension | Assessment |
|---|---|
| Complexity | Medium |
| Migration cost | Medium and additive |
| Semantic safety | High |
| Market analytics | Strong and reproducible |

**Pros:** preserves the current ledger, makes every output inspectable, and
supports both campus and market products without a second truth system.

**Cons:** requires another regression-tested migration before production
deployment and forces indicator definitions to be maintained as versioned
data contracts.

### Option C: Build a separate analytics warehouse now

| Dimension | Assessment |
|---|---|
| Complexity | High |
| Migration cost | High |
| Semantic safety | Medium |
| Market analytics | Strong but duplicated |

**Pros:** flexible analytical queries and large-scale series storage.

**Cons:** creates a second lineage system before volume justifies it, increases
operating burden for one researcher, and risks divergence from published
facts.

## Trade-off analysis

Option B adds bounded schema work now but avoids much more expensive cleanup
after forecasts and aggregates have been published. It keeps PostgreSQL as the
operational truth and generated snapshots as public truth. Large raster and
dense time-series payloads may still live as Parquet or COG objects in R2;
PostgreSQL stores definitions, summaries, and lineage.

## Consequences

- Current, forecast, modeled, and observed values cannot be blended silently.
- Every market card and chart can expose its inputs and methodology.
- Infrastructure and satellite layers can be served by the same snapshot as
  the campus dossiers.
- The M2 production deployment remains pending until the additive semantic
  migration passes regression tests.
- The first public alpha takes slightly longer, but it will not require a data
  model rewrite to add market dossiers.
- Opaque composite scores remain out of scope until their component metrics
  and weights are independently useful and published.

## Action items

1. [x] Add the additive semantic migration and regression scenarios.
2. [ ] Extend normalization and review manifests with `epistemic_type`.
3. [ ] Register the first capacity and delivery-funnel metric definitions.
4. [ ] Normalize Beacon Point's eligible 352 MW assertion only after its
       immutable review decision is sealed.
5. [ ] Include method, coverage, vintage, and input fact IDs in the public
       snapshot contract.
6. [ ] Add infrastructure and satellite observation exports before market-map
       UI work begins.
