# Cropstar

Open-source farm management for regenerative agriculture — built around learning by doing.

Cropstar does not decide for the farmer. It supplies context, background and consequences
so the farmer can make an informed decision. Every number it shows carries an uncertainty
band, a source, and an answer to "why?".

> **Status: Stage 3 in progress.** Landing page and blog in German (default) and English.
> The farm app has started: an API with a PostGIS database, reachable from the web app. The
> simulation model and the data pipeline do not exist yet. See
> [`.github/instructions/general.instructions.md`](.github/instructions/general.instructions.md)
> for the full project charter and the staged plan, [`CONTEXT.md`](CONTEXT.md) for the
> domain vocabulary and [`docs/adr/`](docs/adr) for architecture decisions.

## Repository layout

```
apps/web/             Nuxt 4 app — landing page, blog and the farm app under /app
apps/api/             FastAPI service with PostgreSQL + PostGIS (Python, uv workspace member)
packages/api-client/  Typed TypeScript client, generated from the API's OpenAPI schema
content/              Markdown blog posts
docker/               Production images, full-stack compose and the development database
```

The browser only ever talks to the web origin: the Nuxt server proxies `/api/**` to the
API, so there is no CORS and a self-hosted instance needs one domain. Directories for the
model and the shared contracts are added when the stage that needs them starts.

## Configuration

All of these are optional in development and set as environment variables in production.

Web app:

| Variable | Purpose |
| --- | --- |
| `NUXT_API_BASE_URL` | Where the `/api` proxy forwards to (default `http://localhost:8000`) |
| `NUXT_PUBLIC_CONTACT_EMAIL` | Address behind the contact and early-access buttons |
| `NUXT_PUBLIC_REPOSITORY_URL` | Repository linked from the header and footer |
| `NUXT_PUBLIC_I18N_BASE_URL` | Public origin, required for correct `hreflang` and canonical links |

API:

| Variable | Purpose |
| --- | --- |
| `CROPSTAR_DATABASE_URL` | SQLAlchemy URL of the PostGIS database (`postgresql+psycopg://…`) |
| `CROPSTAR_HOST`, `CROPSTAR_PORT` | Bind address of the API server (default `0.0.0.0:8000`) |
| `CROPSTAR_TEST_DATABASE_URL` | Server the API tests create their throwaway database on |

The full-stack compose file additionally reads `CROPSTAR_DB_PASSWORD` and
`CROPSTAR_WEB_PORT`.

## Prerequisites

- Node.js >= 22 and pnpm 10 (`corepack enable`)
- [`uv`](https://docs.astral.sh/uv/) — installs Python 3.12 and the API's dependencies
- [`just`](https://github.com/casey/just) (optional — every recipe is a plain pnpm or uv command)
- Docker, for the development database and the production images

## Development

```bash
just install       # pnpm install + uv sync
just db-up         # PostGIS on localhost:5432
just api-dev       # migrate, then the API on http://localhost:8000 (docs at /api/docs)
just dev           # web app on http://localhost:3000; /app shows API and database status
just check         # lint, typecheck, test, API client check, build — same as CI
```

After changing the API, regenerate the typed client and commit it with the change:
`just generate-api-client`. CI fails when the committed client is stale.

Database migrations live in the API package (Alembic). Create one from `apps/api` with
`uv run alembic revision -m "…" --rev-id 0002`; the API applies pending migrations when it
starts.

## Container

Two images: `cropstar-web` (Node server, port `3000`, health probe `/healthz`) and
`cropstar-api` (port `8000`, health probe `/api/healthz`). The API migrates the database
when it starts, so run a single API replica. Neither image contains a reverse proxy or
terminates TLS — that is the job of whatever fronts them (Coolify's Traefik, in our
deployment).

`docker/compose.yaml` runs the whole stack — web, API and PostGIS — from a clean checkout.
Only the web app is published; the API and the database stay on the internal network.

```bash
just docker-up       # http://localhost:3000
just docker-health
```

## Deployment

GitHub Actions builds both images on every push to `main` and publishes them to
`ghcr.io/johannespfennigbauer/cropstar-web` and `ghcr.io/johannespfennigbauer/cropstar-api`.
Coolify deploys those prebuilt tags. The application server never builds.

## Licence

AGPL-3.0-only. The simulation model and the contracts will be published under a permissive
licence when they are added, so that researchers can adopt and cite them.
