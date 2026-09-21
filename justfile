set shell := ["bash", "-uc"]

image := "ghcr.io/johannespfennigbauer/cropstar-web"
tag := "dev"

# List available recipes
default:
    @just --list

# Install all workspace dependencies
install:
    pnpm install --frozen-lockfile

# Run the web app in development mode
dev:
    pnpm --filter @cropstar/web dev

# Build the web app for production (Node server output)
build:
    pnpm --filter @cropstar/web build

# Serve the production build locally
preview:
    pnpm --filter @cropstar/web preview

lint:
    pnpm -r lint

typecheck:
    pnpm -r typecheck

test:
    pnpm -r test

# Everything CI runs, in the same order
check: lint typecheck test build

# Build the production container image
docker-build:
    docker build -f docker/Dockerfile -t {{image}}:{{tag}} .

# Run the production image locally on http://localhost:3000
docker-up:
    docker compose -f docker/compose.yaml up --build

docker-down:
    docker compose -f docker/compose.yaml down

# Verify the container answers its health probe
docker-health:
    curl -fsS http://localhost:3000/healthz && echo
