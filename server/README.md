# StormFront — Server

FastAPI service for the StormFront MUD. HTTP for auth + character lifecycle;
WebSocket for the live game session.

## Layout

```
server/
├─ app/
│  ├─ main.py            FastAPI app factory + lifespan
│  ├─ config.py          Env-driven settings
│  ├─ db.py              Motor client + index management
│  ├─ deps.py            Shared FastAPI dependencies (db, current_account)
│  ├─ models.py          Pydantic models mirroring spec/ schemas + AsyncAPI
│  ├─ security.py        Password hashing + JWT issue / verify
│  ├─ world.py           Initial world seed (idempotent)
│  └─ routers/
│     ├─ auth.py         /auth/register, /auth/login, /auth/refresh
│     ├─ characters.py   /characters (list, create)
│     ├─ health.py       /healthz
│     ├─ me.py           /me (current account)
│     └─ websocket.py    /ws (game session)
├─ tests/                Smoke tests (require Mongo)
├─ Dockerfile
├─ .dockerignore
└─ pyproject.toml
```

## Running locally (without Docker)

```bash
# 1. Install in a venv
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 2. Start MongoDB somehow (local install, Docker, Atlas, ...)
#    Default URL: mongodb://localhost:27017

# 3. Run
uvicorn app.main:app --reload
```

OpenAPI docs at <http://localhost:8000/docs>.

## Running via Docker

The repo-root `docker-compose.yml` (TBD) will bring up Mongo, Redis,
and the server. Standalone:

```bash
docker build -t stormfront-server .
docker run -p 8000:8000 \
    -e MONGO_URL=mongodb://host.docker.internal:27017 \
    -e JWT_SECRET=please-change-me-at-least-16-chars \
    stormfront-server
```

## Configuration

All settings are env-driven via `pydantic-settings`. Defaults are dev-safe;
production must override `JWT_SECRET`.

| Env var               | Default                       | Notes                              |
| --------------------- | ----------------------------- | ---------------------------------- |
| `MONGO_URL`           | `mongodb://localhost:27017`   |                                    |
| `MONGO_DB`            | `stormfront`                  |                                    |
| `REDIS_URL`           | `redis://localhost:6379/0`    | reserved for cross-process fan-out |
| `JWT_SECRET`          | `dev-only-change-me`          | required >= 16 chars               |
| `JWT_ALGORITHM`       | `HS256`                       |                                    |
| `JWT_ACCESS_TTL_MIN`  | `15`                          |                                    |
| `JWT_REFRESH_TTL_DAYS`| `30`                          |                                    |
| `CORS_ORIGINS`        | `["http://localhost:5173"]`   | JSON list                          |
| `LOG_LEVEL`           | `info`                        |                                    |

## What the WebSocket scaffold supports

Connect to `ws://localhost:8000/ws?token=<jwt-access-token>`. Expect:

1. `server.welcome` containing your player + room view
2. Respond to `client.ping`, `client.command.look`,
   `client.command.inventory`, `client.command.who`
3. `server.error` with `code: UNIMPLEMENTED` for `move`, `say`, `shout`,
   `take`, `drop`

Cross-player events (`server.player.arrived`, chat, etc.) require a broker;
intentionally not in the scaffold.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The smoke tests require a real MongoDB at `MONGO_URL`. They use a uniquely
named test database that is dropped on teardown.
