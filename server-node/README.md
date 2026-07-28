# StormFront — Server (Node)

NestJS (Express platform) port of `../server` (the FastAPI reference
implementation) for the StormFront MUD. HTTP for auth + character lifecycle;
WebSocket for the live game session.

**Status: scaffolding only.** The app boots, connects to Mongo, and serves
`/healthz` for real. Auth, characters, `/me`, and the game WebSocket protocol
are stubbed — each throws `NotImplementedException` with a pointer to the
Python file to port from. The in-process pub/sub broker
(`src/websocket/broker.service.ts`) is a complete, working port of
`server/app/broker.py` since it's pure infra with no protocol logic.

## Layout

```
server-node/
├─ src/
│  ├─ main.ts                 Bootstrap, CORS, validation pipe, ws adapter
│  ├─ app.module.ts            Root module wiring
│  ├─ config/                  Env-driven settings (mirrors app/config.py)
│  ├─ database/                Mongo client + index management (mirrors app/db.py)
│  ├─ health/                  GET /healthz
│  ├─ auth/                    /auth/register, /auth/login, /auth/refresh (stub)
│  ├─ characters/               /characters (list, create) (stub)
│  ├─ me/                       GET /me (stub)
│  └─ websocket/                /ws game gateway (stub) + broker (real)
├─ Dockerfile
├─ .dockerignore
├─ package.json
└─ tsconfig*.json / nest-cli.json
```

## Running locally (without Docker)

```bash
cd server-node
npm install
npm run start:dev
```

Requires a reachable MongoDB (default `mongodb://localhost:27017`) — same as
the Python server.

## Running via Docker

The repo-root compose files bring up Mongo, Redis, and whichever server you
pick. See the root `README.md` for the exact commands. Standalone:

```bash
docker build -t stormfront-server-node .
docker run -p 8000:8000 \
    -e MONGO_URL=mongodb://host.docker.internal:27017 \
    -e JWT_SECRET=please-change-me-at-least-16-chars \
    stormfront-server-node
```

## Configuration

Same env vars as `../server` (see its README for the full table):
`MONGO_URL`, `MONGO_DB`, `REDIS_URL`, `JWT_SECRET`, `JWT_ALGORITHM`,
`JWT_ACCESS_TTL_MIN`, `JWT_REFRESH_TTL_DAYS`, `CORS_ORIGINS`, `LOG_LEVEL`.

## What's next

Port, in order, using the Python files as the spec:

1. `auth/auth.service.ts` — from `server/app/routers/auth.py` +
   `server/app/security.py` (bcryptjs + jsonwebtoken are already
   dependencies, just not wired up).
2. `me/me.controller.ts` + a bearer-token guard — from
   `server/app/routers/me.py` + `server/app/deps.py`.
3. `characters/characters.service.ts` — from
   `server/app/routers/characters.py` + `server/app/world.py` (world seed).
4. `websocket/game.gateway.ts` — from `server/app/routers/websocket.py`,
   using the already-ported `BrokerService` for fan-out.
5. An NPC scheduler — from `server/app/npc_scheduler.py` (asyncio tasks map
   to a `setTimeout` loop per room).

## Tests

```bash
npm test
```

Currently just the health check. Ported verticals should get integration
tests mirroring `server/tests/`.
