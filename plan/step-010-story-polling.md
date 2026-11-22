# Step 010 — Story: Polling

**Type:** Story · **Slice:** Slice 1 · **Depends on:** 009

## Goal

As the operator, I send an email to the agent's inbox and within a few seconds the log
shows it as `NEW`. Restarting the agent doesn't show it again.

## Context

- [retrieve-classify.md](../docs/retrieve-classify.md#one-poll): the poll flow, full sync,
  `historyId` handling.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/gmail.py` | Add `history.list` since a `historyId`, filtered to `INBOX` and `messageAdded`. Add a full sync of unread inbox IDs. Add the current `historyId` from the profile. |
| `src/email_agent/poller.py` | New. One poll: pick history or full sync, drop known IDs, save each new one as `NEW` with its `thread_id` and `internal_date`, then save the new `historyId`. Returns the new IDs in arrival order. |
| `src/email_agent/db.py` | Add "which of these IDs are known". |
| `src/email_agent/__main__.py` | Loop forever: one poll, log each new ID, sleep `POLL_SECONDS`. |

## What to build

- First start, or a `404` from `history.list`, runs the full sync.
- The `historyId` is saved only after every new email has its `NEW` row.
- Arrival order is `internalDate`, oldest first.

## Acceptance criteria

- [ ] First start on an inbox with unread mail logs each unread email as `NEW`.
- [ ] A new email shows as `NEW` within `POLL_SECONDS` plus a few seconds.
- [ ] A restart logs nothing for emails already seen.
- [ ] `uv run pyright` is clean.

## Out of scope

- Processing the email. Steps 011 and 012 start that.
- Resuming unfinished emails first. Step 016 adds it.
