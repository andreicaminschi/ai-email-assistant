# Step 005 — Story: Label setup

**Type:** Story · **Slice:** Foundation · **Depends on:** 004

## Goal

As the operator, I start the agent against a fresh inbox and every label it needs appears
in Gmail. A second start creates nothing new.

## Context

- [gmail-oauth.md](../docs/gmail-oauth.md#label-setup): the labels, the flow, failure
  handling.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/gmail.py` | Add list labels and create label. |
| `src/email_agent/startup.py` | Add label setup after the account check. Returns a name-to-ID map. |
| `src/email_agent/__main__.py` | Run label setup and log the map's size. |

## What to build

- Required: `MEETING_REQUEST`, `TASK`, `INFO_ONLY`, `SALES_OUTREACH`, `MARKETING`, `URGENT`,
  `Finance`. `SPAM` maps to Gmail's built-in `SPAM` ID and is never created.
- Names match ignoring case, so a hand-made `finance` label is reused.
- The map is a new immutable value returned to the caller. It lives only in memory.
- A failed create logs which label and exits 1.

## Acceptance criteria

- [ ] On an account without the labels, one start creates all seven, visible in Gmail.
- [ ] A second start logs that every label exists and creates none.
- [ ] Renaming `Finance` to `finance` in Gmail, then restarting, reuses it.
- [ ] `uv run pyright` is clean.

## Out of scope

- Applying labels to email. Step 015 does that.
