# Step 029 — Story: README

**Type:** Story · **Slice:** Delivery · **Depends on:** 026

## Goal

As the reviewer, I open the README and can set up credentials, start the agent, run the
live test and read what it did, without opening any other file first.

## Context

- [REQUIREMENTS.md](../docs/REQUIREMENTS.md#deliverables): the README is a deliverable.
- [gmail-oauth.md](../docs/gmail-oauth.md), [config.md](../docs/config.md),
  [containers.md](../docs/containers.md): the facts it points to.

## Files

| File | Change |
| --- | --- |
| `README.md` | New. |

## What to build

Sections, each short, each linking to its doc for depth:

| Section | Holds |
| --- | --- |
| What it does | One paragraph and the (sender, label) handler table. |
| Setup | Create the Desktop OAuth client, add the test user, run the token script, fill `.env` from `.env.example`, put the LLM key in `./secrets/llm_api_key`. |
| Run | Production and dev commands, podman first, then docker. |
| Operate | Answering a forward with yes or no, what the manager and sender receive, reading the audit log from stdout and SQLite. |
| Swap the LLM | Change `LLM_MODEL`, `LLM_BASE_URL` and the key file. No code change. |
| Limits | The 7-day token expiry, explicit meeting dates only, no calendar availability check, replies without a decision word ignored, no Gmail rate-limit handling. |

## Acceptance criteria

- [ ] Following only the README on a clean clone gets the agent to `Connection ready`.
- [ ] Every command appears in a podman and a docker form.
- [ ] Every link resolves.

## Out of scope

- Repeating the design docs. The README links to them.
