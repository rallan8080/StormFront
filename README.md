# StormFront

A spec-driven, containerized MUD (multi-user dungeon) built to demonstrate
modern full-stack patterns outside the .NET ecosystem.

## What this project is

A small, focused MUD where players move between rooms, chat with each other,
pick up and drop items, and interact with stationary NPCs. The goal is not to
ship a feature-complete game; it is to demonstrate end-to-end engineering
across the boundaries of:

- A typed, async Python service exposing both HTTP and WebSocket APIs
- A document database modeled around the natural shape of game entities
- A real-time browser client driven by a strict message contract
- A spec-first workflow where the OpenAPI, AsyncAPI, and JSON Schema files
  in `spec/` are the source of truth for both ends of the wire

## Stack

| Layer            | Choice                                        |
| ---------------- | --------------------------------------------- |
| Backend          | Python 3.12 + FastAPI + native WebSockets     |
| Async DB driver  | Motor (async MongoDB)                         |
| Database         | MongoDB                                       |
| Real-time fan-out| Redis pub/sub (for cross-process scale-out)   |
| Frontend         | React + TypeScript + Vite + xterm.js          |
| Auth             | JWT access + refresh tokens                   |
| Container runtime| Docker + Docker Compose locally               |
| Deploy target    | Azure Container Apps                          |
| CI               | GitHub Actions                                |

## Repository layout

```
stormfront/
├─ spec/
│  ├─ openapi.yaml           HTTP surface (auth, characters)
│  ├─ asyncapi.yaml          WebSocket message catalog
│  └─ schemas/               Shared domain JSON Schemas
│     ├─ exit.json
│     ├─ item.json
│     ├─ npc.json
│     ├─ player.json
│     └─ room.json
├─ server/                   FastAPI service        (TBD)
├─ client/                   React + xterm.js app   (TBD)
├─ docker-compose.yml                              (TBD)
└─ .github/workflows/                              (TBD)
```

## Spec-driven workflow

The contract lives in `spec/`, and everything else is derived from it:

```
       ┌──────────────────────┐
       │   spec/*.json,*.yaml │  source of truth
       └──────────┬───────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
  ┌─────▼──────┐      ┌─────▼──────┐
  │  Python    │      │ TypeScript │
  │  pydantic  │      │   types    │
  │  models    │      │ (codegen)  │
  └─────┬──────┘      └─────┬──────┘
        │                   │
  ┌─────▼──────┐      ┌─────▼──────┐
  │  FastAPI   │      │  React /   │
  │  service   │      │  xterm.js  │
  └────────────┘      └────────────┘
```

Both sides validate against the same schemas. Contract drift is caught at
build time, not at runtime.

## MVP scope

Locked in for the initial release. Everything else is a roadmap item.

- [ ] Account create / login (JWT)
- [ ] Single character per account
- [ ] Fixed world of ~10 rooms with exits
- [ ] Commands: `look [target]` (no target = current room; target = an item,
      NPC, or player to examine), `go <direction>`, `say <message>`,
      `shout <message>`, `take <item>`, `drop <item>`, `inventory`, `who`
- [ ] One stationary NPC type with random dialogue
- [ ] Multi-player visibility: room occupants, arrival / departure events

Explicitly **not** in MVP: combat, leveling, persistent NPC AI, shops,
admin tools, multi-character accounts, world editor.

## Status

Pre-implementation. Specs land first; server and client scaffolding follow.
