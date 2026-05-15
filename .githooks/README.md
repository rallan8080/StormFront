# Git hooks

Tracked git hooks for StormFront. Activated via `git config core.hooksPath`
so the scripts live in the repo (instead of `.git/hooks/`, which isn't
tracked).

## Setup (one-time, per clone)

```sh
git config core.hooksPath .githooks
```

That's it. Hooks fire automatically on subsequent `git commit` / `git push`.

## Hooks

| Hook | What it runs |
|---|---|
| `pre-commit` | `ruff check app tests` inside the running `server` container. Same command as CI. |

## Requirements

The `server` container must be running for `pre-commit` to work:

```sh
docker compose up -d server
```

If the container isn't running, the hook fails loudly with instructions —
it doesn't silently skip.

## Bypass

If you genuinely need to commit without running the hook (e.g. a WIP push
on a feature branch), use `--no-verify`:

```sh
git commit --no-verify -m "wip: experimenting"
```

Use sparingly. CI will still run the same checks on push.
