# Cropstar

Open-source farm management for regenerative agriculture — built around learning by doing.

Cropstar does not decide for the farmer. It supplies context, background and consequences
so the farmer can make an informed decision. Every number it shows carries an uncertainty
band, a source, and an answer to "why?".

> **Status: Stage 1.** Landing page only, in German (default) and English. The simulation
> model, the data pipeline and the farm management app do not exist yet. See
> [`.github/instructions/general.instructions.md`](.github/instructions/general.instructions.md)
> for the full project charter and the staged plan.

## Repository layout

```
apps/web/     Nuxt 4 app — landing page today, blog and farm app later
content/      Markdown blog posts (Stage 2)
docker/       Production image and local compose
```

Directories for the API, the model and the shared contracts are added when the stage that
needs them starts, not before.

## Configuration

All of these are optional in development and set as environment variables in production:

| Variable | Purpose |
| --- | --- |
| `NUXT_PUBLIC_CONTACT_EMAIL` | Address behind the contact and early-access buttons |
| `NUXT_PUBLIC_REPOSITORY_URL` | Repository linked from the header and footer |
| `NUXT_PUBLIC_I18N_BASE_URL` | Public origin, required for correct `hreflang` and canonical links |

## Prerequisites

- Node.js >= 22 and pnpm 10 (`corepack enable`)
- [`just`](https://github.com/casey/just) (optional — every recipe is a plain pnpm command)
- Docker, to build or run the production image

## Development

```bash
just install     # pnpm install --frozen-lockfile
just dev         # http://localhost:3000
just check       # lint, typecheck, test, build — same order as CI
```

## Container

The app ships as a Node server image. It publishes port `3000` and answers a health probe
at `/healthz`. It contains no reverse proxy and terminates no TLS — that is the job of
whatever fronts it (Coolify's Traefik, in our deployment).

```bash
just docker-build
just docker-up       # http://localhost:3000
```

## Deployment

GitHub Actions builds the image on every push to `main` and publishes it to
`ghcr.io/johannespfennigbauer/cropstar-web`. Coolify deploys that prebuilt tag. The
application server never builds.

## Licence

AGPL-3.0-only. The simulation model and the contracts will be published under a permissive
licence when they are added, so that researchers can adopt and cite them.
