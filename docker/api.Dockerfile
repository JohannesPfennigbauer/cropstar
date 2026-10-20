# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependency layer: only manifests and the lockfile, so source edits do not invalidate it.
COPY pyproject.toml uv.lock .python-version ./
COPY apps/api/pyproject.toml ./apps/api/pyproject.toml
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package cropstar-api --no-install-workspace

COPY apps/api ./apps/api
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --package cropstar-api --no-editable


FROM python:3.12-slim-bookworm AS runtime

LABEL org.opencontainers.image.title="cropstar-api" \
      org.opencontainers.image.description="Cropstar farm-app API" \
      org.opencontainers.image.source="https://github.com/JohannesPfennigbauer/cropstar" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

RUN useradd --system --uid 10001 --no-create-home cropstar

ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    CROPSTAR_HOST=0.0.0.0 \
    CROPSTAR_PORT=8000

WORKDIR /app
COPY --from=build --chown=cropstar:cropstar /app/.venv ./.venv

USER cropstar
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/healthz', timeout=2)"

# Migrates the schema, then serves. Run a single replica so migrations never race.
CMD ["cropstar-api", "serve"]
