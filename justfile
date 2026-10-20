set shell := ["bash", "-uc"]

registry := "ghcr.io/johannespfennigbauer"
tag := "dev"

# List available recipes
default:
    @just --list

# Install all workspace dependencies (TypeScript and Python)
install:
    pnpm install --frozen-lockfile
    uv sync --locked

# Run the web app in development mode (proxies /api to http://localhost:8000)
dev:
    pnpm --filter @cropstar/web dev

# Run the API in development mode with auto-reload (needs `just db-up`)
api-dev: api-migrate
    CROPSTAR_ENVIRONMENT=development uv run uvicorn cropstar_api.app:create_app --factory --reload --port 8000

# Demo Farm with real INVEKOS Fields and Plots; sign in as demo@cropstar.local / cropstar-demo
seed: api-migrate
    CROPSTAR_ENVIRONMENT=development uv run cropstar-api seed-demo

# Reset a user's password and sign them out everywhere (Instance Operator)
reset-password email:
    uv run cropstar-api reset-password {{email}}

# Upgrade the development database to the latest migration
api-migrate:
    uv run cropstar-api migrate

# Start the development PostGIS database on localhost:5432
db-up:
    docker compose -f docker/compose.dev.yaml up -d --wait

db-down:
    docker compose -f docker/compose.dev.yaml down

# Build the web app for production (Node server output)
build:
    pnpm --filter @cropstar/web build

# Serve the production build locally
preview:
    pnpm --filter @cropstar/web preview

lint:
    pnpm -r lint
    uv run ruff check .
    uv run ruff format --check .

typecheck:
    pnpm -r typecheck
    uv run mypy

# Web unit tests and API tests (the API tests need `just db-up`)
test:
    pnpm -r test
    uv run pytest

# Browser tests against the production web build, a real API and PostGIS (needs `just db-up`).
# First time: `pnpm --filter @cropstar/web exec playwright install --with-deps chromium`
e2e: build
    pnpm --filter @cropstar/web test:e2e

# Regenerate the typed API client from the API's OpenAPI schema; commit the result
generate-api-client:
    uv run cropstar-api openapi packages/api-client/openapi.json
    pnpm --filter @cropstar/api-client generate

# Fail if the committed API client differs from a fresh generation
check-api-client:
    #!/usr/bin/env bash
    set -euo pipefail
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    uv run cropstar-api openapi "$tmp/openapi.json"
    pnpm --silent --filter @cropstar/api-client exec openapi-typescript "$tmp/openapi.json" -o "$tmp/schema.d.ts" > /dev/null
    if ! diff -u packages/api-client/openapi.json "$tmp/openapi.json" \
        || ! diff -u packages/api-client/src/schema.d.ts "$tmp/schema.d.ts"; then
        echo "The API client is stale. Run 'just generate-api-client' and commit the result." >&2
        exit 1
    fi

# Everything CI runs, in the same order
check: lint typecheck test check-api-client build

# Build both production container images
docker-build:
    docker build -f docker/web.Dockerfile -t {{registry}}/cropstar-web:{{tag}} .
    docker build -f docker/api.Dockerfile -t {{registry}}/cropstar-api:{{tag}} .

# Run the full stack (web, API, PostGIS) on http://localhost:3000
docker-up:
    docker compose -f docker/compose.yaml up --build

docker-down:
    docker compose -f docker/compose.yaml down

# Verify the running stack answers its health probes, the API through the web origin
docker-health:
    curl -fsS http://localhost:${CROPSTAR_WEB_PORT:-3000}/healthz && echo
    curl -fsS http://localhost:${CROPSTAR_WEB_PORT:-3000}/api/status && echo
