# syntax=docker/dockerfile:1.7

# ---- deps ----
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install

# ---- build ----
FROM deps AS build
COPY tsconfig*.json nest-cli.json ./
COPY src ./src
RUN npm run build

# ---- runtime ----
FROM node:22-slim AS runtime

ENV NODE_ENV=production \
    PORT=8000

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system app \
 && useradd --system --gid app --home /app --shell /usr/sbin/nologin app

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --omit=dev
COPY --from=build /app/dist ./dist

USER app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --retries=3 \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

CMD ["node", "dist/main.js"]


# ---- dev (testing / local development) ----
#
# Full dev deps (nest CLI watch mode, jest, eslint) plus source baked in.
# Selected by docker-compose.node.override.yml via `build.target: dev`.
# Production builds use `target: runtime` (see docker-compose.node.yml).
FROM deps AS dev

ENV PORT=8000

COPY . .

EXPOSE 8000

CMD ["npm", "run", "start:dev"]
