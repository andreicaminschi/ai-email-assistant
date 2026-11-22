# Step 007 — Story: Wrapper endpoint

**Type:** Story · **Slice:** Containers · **Depends on:** 001

## Goal

As the developer, I can point an OpenAI-style client at a local endpoint and get Claude's
answer back as a `final_result` tool call, paid for by my Claude subscription.

## Context

- [containers-dev.md](../docs/containers-dev.md): the whole wrapper design, request
  handling, status codes, system prompt.

## Files

| File | Change |
| --- | --- |
| `pyproject.toml`, `uv.lock` | Add a `wrapper` dependency group: `fastapi`, `uvicorn`. |
| `src/wrapper/__init__.py` | New, empty. Boilerplate. |
| `src/wrapper/claude_cli.py` | New. Builds the system prompt from the fixed line, the request's system prompt and the tool's schema. Runs `claude -p` with tools off and a timeout. Returns stdout or a typed failure. |
| `src/wrapper/server.py` | New. FastAPI app with `POST /v1/chat/completions`. Rejects streaming and any tool but `final_result`. Maps failures to `502` and `504`. Wraps stdout as a `final_result` tool call. |
| `docs/config.md` | Add the wrapper timeout, 120 seconds, to "Fixed in code". |

## What to build

- The fixed line's wording is settled here, starting from the draft in the doc.
- The token is read from `/run/secrets/claude_token` and passed as
  `CLAUDE_CODE_OAUTH_TOKEN` to each `claude -p` run only.
- The response follows the OpenAI chat completion shape that Pydantic-AI's OpenAI
  provider parses.
- The wrapper never checks the JSON itself.

## Acceptance criteria

- [ ] On the host, with `claude` installed and logged in,
      `uv run --group wrapper uvicorn wrapper.server:app --port 8000` starts.
- [ ] A POST with a `final_result` tool returns `200` and a tool call whose arguments are
      Claude's JSON.
- [ ] A POST with `"stream": true` returns `400`.
- [ ] `uv run pyright` is clean.

## Out of scope

- The container image and compose service. Step 008 adds them.
