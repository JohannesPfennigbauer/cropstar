# syntax=docker/dockerfile:1

FROM node:22-alpine AS build

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH
RUN corepack enable

WORKDIR /app

# Dependency layer: only manifests, so source edits do not invalidate the install.
# Scripts are skipped here because `nuxt prepare` needs sources that arrive below.
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile --ignore-scripts

COPY . .
RUN pnpm --filter @cropstar/web build


FROM node:22-alpine AS runtime

LABEL org.opencontainers.image.title="cropstar-web" \
      org.opencontainers.image.description="Cropstar landing page and farm app" \
      org.opencontainers.image.source="https://github.com/JohannesPfennigbauer/cropstar" \
      org.opencontainers.image.licenses="AGPL-3.0-only"

ENV NODE_ENV=production \
    NITRO_PORT=3000 \
    NITRO_HOST=0.0.0.0

WORKDIR /app
COPY --from=build --chown=node:node /app/apps/web/.output ./.output

USER node
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:3000/healthz').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", ".output/server/index.mjs"]
