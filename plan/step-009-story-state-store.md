# Step 009 — Story: State store

**Type:** Story · **Slice:** Slice 1 · **Depends on:** 006

## Goal

As the operator, I start the agent and it creates its SQLite file in the `agent-data`
volume, ready to remember emails and the last `historyId`.

## Context

- [state-audit.md](../docs/state-audit.md#tables): the `emails` and `meta` columns.
- [containers.md](../docs/containers.md#inspecting-state): where the file lives.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/db.py` | New. Opens `DATA_DIR/agent.db`, creates `emails` and `meta` if missing. Functions to insert an email row, read one, change its state, and get or set `history_id`. |
| `src/email_agent/__main__.py` | Open the database after label setup. |

## What to build

- Only `emails` and `meta` now. `audit`, `sends` and `approvals` arrive with the steps
  that first need them: 012, 020 and 022.
- Schema creation is safe to repeat on every start.
- State values are the names from the state catalog, stored as text.
- Each function takes the connection and plain values, and returns new values. Nothing
  passed in is changed.

## Acceptance criteria

- [ ] After `podman compose up`, `podman compose exec app sqlite3 /data/agent.db .tables`
      lists `emails` and `meta`. Use `python -c` with `sqlite3` if the CLI isn't in the
      image.
- [ ] Restarting keeps the file and its rows.
- [ ] `podman compose down -v`, then `up`, starts with an empty file.
- [ ] `uv run pyright` is clean.

## Out of scope

- Writing rows from real mail. Step 010 does that.
