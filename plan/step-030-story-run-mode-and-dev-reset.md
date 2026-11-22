# Step 030 — Story: Run mode and dev reset

**Type:** Story · **Slice:** Dev · **Depends on:** 010

## Goal

As the operator, I set `RUN_MODE=dev` and each start puts the emails the agent already
processed back to `NEW`, with the agent's labels removed, so the same inbox runs again.
`RUN_MODE=prod` changes nothing.

## Context

- [config.md](../docs/config.md#env-variables): `RUN_MODE`.
- [classify-tree.md](../docs/classify-tree.md#dev-mode): what dev mode does per label.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/config.py` | `RunMode` enum (`dev`, `prod`) and a required `run_mode` field. |
| `src/email_agent/startup.py` | `set_up_labels` takes the run mode. In dev, it also ensures `This is spam` and `This is archived`. |
| `src/email_agent/gmail.py` | Remove label IDs from one message. A `404` returns false. |
| `src/email_agent/db.py` | Read rows past `NEW`, put a row back to `NEW` with `attempts`, `internal` and `triage` cleared, drop a row. |
| `src/email_agent/__main__.py` | In dev, after `Database ready`, run the reset and print `Dev reset: <n> emails`. |

`.env.example` gets `RUN_MODE=dev`.

## What to build

- Agent labels are the required labels plus the two dev labels. Gmail's own labels and
  `UNREAD` stay.
- A reset row whose message is gone from Gmail is dropped.
- The full sync lists `INBOX` only in dev, so read mail is picked up too. Prod keeps
  `INBOX` and `UNREAD`. `__main__.py` picks the labels, and the poller uses them as given.
- Later tables, such as `sends` and `approvals`, join the reset in the step that adds
  them, if dev mode writes to them.

## Acceptance criteria

- [ ] No `RUN_MODE` stops startup with `Missing required setting RUN_MODE`.
- [ ] `RUN_MODE=prod` prints `Labels ready: 8` and no reset line.
- [ ] `RUN_MODE=dev` creates the two dev labels and prints `Labels ready: 10`, then
      `Dev reset: 0 emails`.
- [ ] A row set to `DONE` in SQLite, with `MARKETING` on its email, is back to `NEW` after
      a dev restart, and the label is gone in Gmail.
- [ ] With a fresh database, a dev start logs read inbox emails as `NEW` too. A prod start
      logs unread ones only.
- [ ] `uv run pyright` is clean.

## Out of scope

- The dev switches inside handlers. Steps 020, 021, 022, 024, 025 and 026 add them.
