---
applyTo: '**'
description: 'Cropstar project charter: philosophy, architecture boundaries, product rules, data strategy, and development stages.'
---

# Cropstar — General Instructions

Cropstar is an open-source farm management application (web + mobile) built around
regenerative agriculture and life-long learning.

**Core philosophy: the app does not decide for the farmer.** It supplies context,
background, and consequences so the farmer can make an informed decision about what and
how to plant and fertilize. Learning is the product; the simulation is the teaching aid.

---

## 1. Product rules (non-negotiable)

These are review criteria, not aspirations. A change that violates one of these is
rejected regardless of how useful it seems.

1. **No bare numbers.** Every model output renders with its uncertainty band and its
   provenance: model version, inputs used, and whether it is an observation or a
   simulation. A number without a band and a source does not render.
2. **Scenarios, not recommendations.** The UI compares user-defined what-if scenarios
   side by side. It never ranks them, never labels one "best" or "recommended", and never
   auto-fills an optimum. The farmer defines the scenarios; the app shows consequences.
3. **Always answer "why".** Any displayed state (water stress, N deficit, BBCH stage)
   must expose the drivers that produced it. If it cannot be explained, it is not shown.
4. **Warnings describe, never prescribe.** "Soil moisture has been below X for 12 days" —
   never "irrigate now."

### Tone and experience

- Aim for a **game-like character**: enjoyable, visual, exploratory. Especially in the
  teaching parts. Exploration of cause and effect should feel rewarding.
- Teach the *impact* of regenerative practices on soil, water, nutrients and environment —
  through interaction, not through walls of text.
- Uncertainty is content, not a disclaimer. Showing the farmer where the model is unsure
  is part of the lesson.
- **The teaching layer is cross-cutting, not a stage.** Every stage ships its own share of
  it — the blog, the plot overview, the simulation results, the scenario comparison. There
  is no phase where learning gets added at the end.

---

## 2. Architecture

### Monorepo, strict boundaries

Single repository, hard package boundaries:

```
apps/web            Landing page (one-pager) + farm management app, installable as PWA
apps/api            FastAPI backend
packages/*          Shared TypeScript (UI, domain types, generated model client)
contracts/          Versioned JSON Schema / OpenAPI — source of truth
model/              Python: plant simulation model, own pyproject.toml, own CI, own README
content/            Markdown blog posts (regenerative practices, crop modeling)
```

`model/` must remain self-contained and independently publishable (PyPI, and
`git subtree split` into its own repo if ever needed). It has no knowledge of the app.

### The app ↔ model boundary

- **Contract-first.** `contracts/` is the source of truth. The Python implementation and
  the TypeScript client are both validated against it. Neither side imports the other's
  internals.
- **Two transports, one contract.** The model is usable as (a) a plain Python
  library/CLI with zero app dependencies, for researchers, and (b) a stateless HTTP
  service the app calls.
- **The model is stateless.** No database access, no user or farm concepts, no hidden
  state. Same request in → same result out.
- **Farm-specific data is passed explicitly** in the request payload: site (lat/lon, soil
  horizons), daily weather series, seeding configuration, planned fertilization and
  irrigation events, species parameters. The app owns and persists all of it.
- Swapping the baseline model for an ML model must be a **configuration change**, never a
  refactor.

### What "the contract" is, concretely

A versioned, machine-readable specification of the model's inputs and outputs, owned by
neither side:

```
contracts/
  cropstar_contract/   pydantic v2 models: SimulationRequest, SimulationResponse
  schema/v1/           generated JSON Schema + OpenAPI, committed to git
  tests/               conformance suite every implementation must pass
```

- `SimulationRequest`: site (lat/lon, soil horizons), daily weather series, species and
  cultivar parameters, seeding configuration, management events (fertilization,
  irrigation), simulation settings. Every field carries units and valid ranges.
- `SimulationResponse`: daily time series per output variable, each with an uncertainty
  band, plus model id and version.
- The schema is **committed**, so contract changes appear in code review. Semver: additive
  changes are minor, everything else is a new major version directory.
- TypeScript types are **generated from the schema in CI**, so the frontend cannot drift.
- The **conformance suite** is the point: baseline and ML implementations pass the same
  tests. That is what makes swapping them a configuration change.

### Tech stack

| Layer | Choice |
| --- | --- |
| Frontend | Nuxt 4 (Vue 3, TypeScript). SSG landing page, Nuxt Content for the markdown blog, SPA for the farm app |
| Mobile | The same Nuxt app as an installable, offline-capable PWA. Capacitor only if native device access is later required |
| Styling / UI | Tailwind + Nuxt UI, with hand-written SVG for the game-like visuals |
| Charts | ECharts for time series; bespoke SVG/D3 for BBCH plant drawings, soil nutrient bubbles and scenario comparison |
| Map | MapLibre GL JS, basemap.at as basemap, own vector layer for boundaries, Sentinel-2 as raster/COG |
| Backend | FastAPI, Python 3.12+, pydantic v2 |
| Auth | **OIDC through an interface**, with a built-in provider (users in our own Postgres) as the default for local and self-hosted instances. Keycloak/Zitadel must remain swappable by configuration. No proprietary auth SaaS — it would break self-hosting |
| Database | PostgreSQL + PostGIS, SQLAlchemy 2.0, Alembic, GeoAlchemy2 |
| Background jobs | arq + Redis (satellite ingestion, simulation runs) |
| Geo / raster | rasterio, rioxarray, xarray, shapely, geopandas, pystac-client, odc-stac |
| Object storage | MinIO (S3 API) for cached rasters and per-plot arrays |
| Tooling | uv workspace (Python) + pnpm workspace (TS), `just` as task runner |
| Tests | pytest, vitest, Playwright |
| Deployment | Docker Compose |

Desktop web is the main product. Mobile serves quick look-ups and data entry (tasks,
observations) — it is not a second full client.

### Simulation design

- Single-plant model that **steps daily**, streaming changing environment conditions,
  taking multiple inputs and producing multiple outputs.
- Wrapped in an **agent-based orchestration layer** so companion planting, intercropping
  and agroforestry can be simulated as interacting agents sharing light, water and
  nutrients.
- The single-plant architecture must be **generalist across plant families** — species as
  an input, one model for all, rather than one model per crop.

---

## 3. Model strategy

### Baseline first

1. Ship a **deterministic process-based baseline** (SIMPLE / AquaCrop-style) behind the
   model contract. The app, the agent layer and the UI are built and validated against it.
2. Use the baseline to generate **high-volume synthetic training data** so the ML model
   learns structure.
3. **Fine-tune on real observed data** (e.g. global intercrop/monocrop cereal–legume trial
   datasets; more to be sourced).
4. Replace the baseline per-output, only when the gate below is met.

Synthetic pretraining buys *capability*, not accuracy: a generalist multi-species model,
differentiability for cheap what-if analysis, and a sequence architecture that can ingest
irregular real signals mid-season. It cannot make the model more accurate than its teacher.

### ML architecture

A **purpose-built CNN-xLSTM**, owned outright and permissively licensed.
The architecture must provide what a generic forecaster does not:

- **Species conditioning** — species and cultivar as inputs, one model for all crops.
- **Masked multi-output head** — see partial supervision below.
- **Physical constraints** — mass balance, and monotonicity for cumulative outputs and
  BBCH stage.
- **Distributional output** — quantiles, not point estimates, because product rule 1
  requires an uncertainty band.
- **Driver-conditioned, not autoregressive** — the model responds to weather and
  management, it does not merely extrapolate its own history.

### Outputs — two tiers

Model design and outputs follow **what data is actually available**.

**Validated tier** — the model is judged on these:

| Variable | Source | Perspective it covers |
| --- | --- | --- |
| Yield | Farmer entry | Season outcome |
| Grain nitrogen / protein | Farmer entry | Quality, N balance |
| BBCH stage | Farmer entry + S2 phenology metrics | Development timing |
| Plant height | Farmer entry | Structure |
| LAI | Sentinel-2 biophysical retrieval | Canopy size, light interception |
| fCover | Sentinel-2 biophysical retrieval | Ground cover, erosion, living-cover days |
| CCC (canopy chlorophyll, Cab × LAI) | Sentinel-2 red edge | Nitrogen status |
| CWC (canopy water content) | Sentinel-2 SWIR | Water status |

**Diagnostic tier** — shown to the user, never an evaluation gate: biomass, nitrogen
uptake. Expensive to measure and scarce; do not anchor evaluation on them.

**Deliberately excluded from evaluation:**

- **fAPAR** — near-deterministic in LAI and sun geometry. Redundant.
- **NDVI** — display only. Farmers recognise it, so show it, but it saturates near canopy
  closure and duplicates LAI/fCover. Never an evaluation target.

Use the Sentinel-2 biophysical retrieval (SNAP / S2ToolBox neural nets) rather than
hand-rolled indices: it returns physical quantities directly comparable to the model's own
state variables. These are **retrievals, not measurements** — they carry real uncertainty
(LAI saturates around 4–5), require cloud and shadow masking, need inward buffering from
field edges because of 10–20 m mixed pixels, and yield far fewer usable observations than
the 5-day revisit suggests. All of that must reach the UI under product rule 1.
Sentinel-1 backscatter is the natural later addition — cloud-independent, sensitive to
canopy structure and surface soil moisture.

### Training rules

- **Partial supervision is the norm.** Loss is masked per-variable — almost no sample
  will have every output. Never require a complete label set.
- **Replacement gate.** The ML model replaces the baseline for a given output only when it
  beats the baseline on a held-out **real** dataset. Until then both remain selectable and
  the baseline stays the default.
- **Continuous improvement loop.** Farmer-contributed observations are realistically
  limited to yield, grain nitrogen/protein, and occasionally BBCH stage and plant height.
  Complement these with continuously arriving satellite-derived variables for validation
  and further training.
- Every model version is identified and pinned. Results are always attributable to a
  specific version.

---

## 4. Data sources

**Initial region: Austria.**

| Domain | Default | Secondary |
| --- | --- | --- |
| Weather | GeoSphere Austria (INCA / SPARTACUS) | Open-Meteo |
| Imagery / indices | Sentinel-2 L2A via Copernicus Data Space | — |
| Soil | eBOD2 — digitale Bodenkarte (BFW), free 1 × 1 km raster | SoilGrids outside coverage |

The free eBOD2 raster is 1 × 1 km. Since almost every plot falls inside a single cell,
soil is effectively constant across neighbouring fields and no within-field variation is
captured. Treat modelled soil as **low-confidence input**, propagate that into the output
uncertainty band, and say so in the UI. Farmer-entered soil lab analyses always override
modelled soil data and should be actively encouraged.

### Rules

- **Provider abstraction from day one.** `WeatherProvider` / `ImageryProvider` interfaces
  with more than one implementation. No vendor is load-bearing. Never call a vendor SDK
  from UI code.
- **Cloud masking is mandatory** for any Sentinel-2 derived index (use the scene
  classification layer), otherwise the NDVI series is unusable.
- **Server-side and cached.** Fetch → clip to plot geometry → compute per-plot statistics
  → store the small numbers. Never proxy raw tiles through the client. Treat every
  provider as if it will be offline.
- **Persist everything the model consumed.** A run must be reproducible years later, so
  store the actual weather and index series used — not a reference to a live API.
- **Field geometry stays ours.** PostGIS, GeoJSON in and out, no vendor lock-in on
  boundaries.

---

## 5. Governance and privacy

- App: **AGPL-3.0** (keeps SaaS forks open). Model code and contracts: **permissive**
  (Apache-2.0/MIT) so researchers and other tools can adopt and cite the model.
- Model weights and a later SaaS offering are **open decisions** — see §8.
- Farm boundaries, yields and grain quality are **commercially sensitive**. Treat them
  accordingly; trust lost here is not recoverable.
- Contributing data to model training is **opt-in, per dataset, revocable, and off by
  default**. It is never a condition of use.
- Contributed observations are stored **de-identified and de-located** — no coordinates in
  the training set.
- **Self-hosting is a first-class scenario.** A farmer, co-operative or advisory service
  must be able to run their own instance from a clean checkout. No mandatory external
  service, no hardcoded vendor.

---

## 6. Do's and Don'ts

**Do**

- Put the contract first; generate or validate clients from it.
- Keep `model/` publishable on its own, at all times.
- Show uncertainty, provenance and drivers alongside every number.
- Make the baseline the default until the ML model earns its place on real data.
- Cache external data and persist what the model consumed.
- Make learning interactive and enjoyable.

**Don't**

- Don't let the app depend on the ML model existing.
- Don't give the model database access or farm/user concepts.
- Don't add a "recommended rate", an auto-optimum, or a ranked suggestion. Ever.
- Don't display a value you cannot explain.
- Don't evaluate the model on biomass, N uptake, NDVI or fAPAR.
- Don't build vendor SDK calls into UI code.
- Don't ship a number without a band and a source.
- Don't collect or train on farm data without explicit opt-in consent.

---

## 7. Development stages

**Stage 0 — Foundations.** Repo, licenses, CI, monorepo skeleton, tooling.

**Stage 1 — Landing page.** One-pager: header, about, sign-in, contact.

**Stage 2 — Blog.** Markdown-driven via Nuxt Content: regenerative practices and crop
modeling. First delivery of the teaching layer.

**Stage 3 — Farm management app, without simulation.** Auth, plot management, geometry
drawing and import, satellite basemap with field boundaries, tasks, observation and
management data entry, dashboard shell, mobile PWA. **Draft the input side of the model
contract here** — otherwise the app will not collect the fields the model later needs
(seeding configuration, fertilization events, soil).

**Stage 4 — Data pipeline.** Provider abstractions, GeoSphere / Open-Meteo weather,
Sentinel-2 ingestion with cloud masking, biophysical retrieval and per-plot statistics,
eBOD soil ingestion, caching and reproducible run persistence.

**Stage 5 — Process-based baseline model.** Contract v1 finalised. Daily-step single-plant
model as a Python library + CLI + thin service, passing the conformance suite. Detail view
shows results and forecast.

**Stage 6 — Agent-based multi-species simulation.** Companion planting, intercropping,
agroforestry via interacting single-plant agents sharing light, water and nutrients.

**Stage 7 — Scenario comparison.** Side-by-side user-defined what-if scenarios with driver
explanations. Never ranked.

**Stage 8 — ML model.** Real-dataset sourcing first (no real-data pipeline → no ML work),
then synthetic pretraining on baseline output, fine-tuning on observed data, per-output
replacement gate, continuous improvement loop from opt-in user data and satellite
observations.

Stages are ordered by dependency, not by calendar, and overlap freely. The teaching layer
is built inside every stage, never deferred to a stage of its own.

---

## 8. Open decisions

- Additional real observed training datasets beyond the intercrop/monocrop trials.
- How simulation results and scenario comparisons are actually presented in the UI.
- Licensing of trained model weights (likely not open) and the shape of a later SaaS
  offering.
