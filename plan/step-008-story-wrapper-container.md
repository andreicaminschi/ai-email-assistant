# Step 008 — Story: Wrapper container

**Type:** Story · **Slice:** Containers · **Depends on:** 006, 007

## Goal

As the developer, I run the dev profile and the app can reach the wrapper at
`http://wrapper:8000`, while nothing on my machine or LAN can.

## Context

- [containers-dev.md](../docs/containers-dev.md#lockdown): no ports, non-root, tools off.
- [containers.md](../docs/containers.md#image-build): the wrapper branch of the build.

## Files

| File | Change |
| --- | --- |
| `Containerfile` | Add a `wrapper` target: `uv sync --frozen --no-dev --group wrapper`, copy `src`, install Claude Code with the pinned native installer, non-root user, run uvicorn on port 8000. |
| `compose.yaml` | Add the `wrapper` service under the `dev` profile, with only the `claude_token` secret and no `ports:`. |

## What to build

- The Claude Code version is pinned in the `Containerfile`.
- `app` gets no access to `claude_token`, and `wrapper` gets no Google token.

## Acceptance criteria

- [ ] `podman compose --profile dev up --build` starts both services.
- [ ] `docker compose --profile dev up --build` does the same.
- [ ] `podman compose --profile dev run --rm --no-deps app /app/.venv/bin/python -c` with a
      short `urllib` POST to `http://wrapper:8000/v1/chat/completions` gets `200`. `exec`
      doesn't work yet, because `app` exits after startup until step 010 adds the poll loop.
- [ ] `curl http://localhost:8000` from the host fails to connect.
- [ ] `uv run pyright` is clean.

## Out of scope

- Calling the wrapper from the agent's code. Step 014 does that.
