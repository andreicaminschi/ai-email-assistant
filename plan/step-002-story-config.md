# Step 002 — Story: Config loading

**Type:** Story · **Slice:** Foundation · **Depends on:** 001

## Goal

As the developer, I start the agent and it either has every setting it needs or tells me
which one is missing, before it touches any API.

## Context

- [config.md](../docs/config.md): every variable, secret file and fixed value.
- [containers.md](../docs/containers.md#decisions): secrets are files, never env vars.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/config.py` | New. A frozen settings model loaded from the environment, plus a function that reads one secret file by name. |
| `src/email_agent/__main__.py` | Load the settings first. A missing or invalid value logs one line and exits 1. |
| `docs/config.md` | Add `SECRETS_DIR` (default `/run/secrets`) and `DATA_DIR` (default `/data`), so the agent also runs on the host. |
| `.env.example` | Add the two new variables, commented out. |

## What to build

- Every variable in `config.md` becomes one typed field. Lists split on commas, trimmed,
  lower-cased. `MEETING_DEFAULT_TIME` parses into a clock time, and
  `MEETING_DURATION_MINUTES` into a positive whole number. `TIME_ZONE` must be a valid
  IANA zone.
- Required variables without a value fail with `Missing required setting AGENT_EMAIL`, one
  line, no stack trace.
- Secret files are read on demand from `SECRETS_DIR`, never cached in an env var.
- On the host, `.env` is loaded by `uv run --env-file .env`. No dotenv dependency.

## Acceptance criteria

- [ ] With `TIME_ZONE` removed from `.env`, `uv run --env-file .env python -m email_agent`
      prints `Missing required setting TIME_ZONE` and exits 1.
- [ ] With a full `.env`, it prints the startup line and the loaded `AGENT_EMAIL`.
- [ ] `TIME_ZONE=Mars/Base` fails with a line naming `TIME_ZONE`.
- [ ] `uv run pyright` is clean.

## Out of scope

- Reading the token files. Step 004 does that.
