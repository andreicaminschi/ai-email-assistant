# Step 006 — Story: App container

**Type:** Story · **Slice:** Containers · **Depends on:** 005

## Goal

As the operator, I run `podman compose up` and the agent passes its startup check inside a
container, with tokens mounted as secrets and nothing secret in the image.

## Context

- [containers.md](../docs/containers.md): services, secrets, volume, image build.
- [config.md](../docs/config.md#secrets): which secret goes where.

## Files

| File | Change |
| --- | --- |
| `Containerfile` | New. Multi-stage build on Astral's uv Python 3.14 slim image. An `app` target: `uv sync --frozen --no-dev`, copy `src`, non-root user, run `python -m email_agent`. |
| `compose.yaml` | New. The `app` service: `env_file: .env`, secrets `gmail_token`, `calendar_token`, `llm_api_key` from `./secrets`, the `agent-data` volume at `/data`, no ports. |
| `.dockerignore` | New. Excludes `secrets/`, `.env`, `tmp/`, `.venv/`, `.git/`. Podman reads it too. |

## What to build

- Compose secrets use `file:` entries, so docker needs no Swarm.
- Secret names in compose match the file names the code reads under `/run/secrets`.
- The app exits 0 after startup for now. Step 010 turns it into a loop.

## Acceptance criteria

- [ ] `podman compose up --build` shows `Connection ready` and the label map in the log.
- [ ] `docker compose up --build` shows the same.
- [ ] `podman image inspect` history shows no layer copying `secrets/`.
- [ ] `uv run pyright` is clean.

## Out of scope

- The `wrapper` service. Step 008 adds it.
