# Step 016 — Story: Retries and crash recovery

**Type:** Story · **Slice:** Slice 1 · **Depends on:** 015, 013

## Goal

As the operator, a failing LLM call or a crash never loses an email and never loops on it
forever. The agent keeps polling either way.

## Context

- [retrieve-classify.md](../docs/retrieve-classify.md#retries-and-crash-recovery): the
  failure table and the attempt counter.
- [gmail-oauth.md](../docs/gmail-oauth.md#startup-check): token failures exit, mid-run too.
- `docs/llm-prompts.md` from step 013: retry and backoff values.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/llm.py` | Add backoff around a call for API errors, wrapper `502` and `504`. Output retries go through Pydantic-AI's own retry setting. |
| `src/email_agent/process.py` | An email past 3 attempts goes straight to `NEEDS_REVIEW`. Exhausted retries go to `NEEDS_REVIEW` with an audit entry. |
| `src/email_agent/poller.py` | Each poll first resumes every unfinished email in arrival order, before fetching new mail. |
| `src/email_agent/google_auth.py` | A refresh failure mid-run raises the same typed error as at startup. |
| `src/email_agent/__main__.py` | That error logs which token failed and exits 1. |

## What to build

- Unfinished means any non-final state except `AWAITING_APPROVAL`.
- The attempt counter goes up before any step runs, so a crash still counts.
- `NEEDS_REVIEW` entries carry a detail such as `retries ran out` or `attempts ran out`.

## Acceptance criteria

- [ ] With the wrapper stopped, a new email is retried with backoff, then logged as
      `NEEDS_REVIEW`, and the next email is still processed.
- [ ] Killing the app while an email is `CLASSIFYING`, then restarting, finishes that email
      before any new one.
- [ ] Setting an email's `attempts` to 3 in SQLite and its state to `CLASSIFYING` sends it
      to `NEEDS_REVIEW` on the next poll.
- [ ] `uv run pyright` is clean.

## Out of scope

- Gmail or Calendar `429` and `5xx` handling. The docs leave it out of the demo.
