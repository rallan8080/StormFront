# syntax=docker/dockerfile:1.7

# ---- deps (install node_modules once, cached) ----
FROM node:22-alpine AS deps

WORKDIR /app

COPY package.json package-lock.json* ./

# npm ci needs a lockfile; on first build there isn't one, so fall back to install.
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi


# ---- builder (production bundle) ----
FROM deps AS builder

COPY . .

RUN npm run build


# ---- dev (Vite dev server with HMR) ----
#
# Source comes from the docker-compose.override.yml bind mount, not COPY,
# so edits hot-reload without a rebuild. An anonymous volume on
# /app/node_modules in compose preserves the container's installed deps
# even though /app is overlaid by the host.
FROM deps AS dev

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]


# ---- runtime (production: static files via nginx) ----
FROM nginx:1.27-alpine AS runtime

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
