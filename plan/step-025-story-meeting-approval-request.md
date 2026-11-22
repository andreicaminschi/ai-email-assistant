# Step 025 — Story: Meeting forward or date request

**Type:** Story · **Slice:** Slice 5 · **Depends on:** 024

## Goal

As the manager, a meeting request with a date reaches me as a forward naming the slot. A
sender who gave no explicit date is asked for one, and I'm not bothered.

## Context

- [calendar-scheduling.md](../docs/calendar-scheduling.md#decisions): start and length
  from the date, time and defaults.
- [classify-tree.md](../docs/classify-tree.md#step-order): the two `MEETING_REQUEST` rows.
- [email-templates.md](../docs/email-templates.md): Approval: meeting, Ask for a date and
  time.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/approval/forward.py` | Add the meeting forward, with `{slot}` from the computed start and end. |
| `src/email_agent/dispatch.py` | `MEETING_REQUEST`: labels, then the forward when there's a date, or Ask for a date and time to the sender when there isn't. Internal `MEETING_REQUEST` uses the same handler. |
| `src/email_agent/process.py` | With a date: save the approval of kind `MEETING` with `meeting_start` and `meeting_end`, `AWAITING_APPROVAL`, action `forward_for_approval`. Without one: `DONE`, action `ask_for_date`. |
| `src/email_agent/db.py` | Save `meeting_start` and `meeting_end` on the approval. |

## What to build

- Start is `meeting_date` at `meeting_time`, or at `MEETING_DEFAULT_TIME`. End is start
  plus `MEETING_DURATION_MINUTES`.
- No calendar is read. Availability isn't checked in v1.

## Acceptance criteria

- [ ] "Can we meet Thu 26 Nov 2026?" sends the manager "Meeting request: ..." for Thu
      26 Nov 10:00–10:30.
- [ ] "Thu 26 Nov at 14:00" names 14:00–14:30.
- [ ] "Can we meet next week?" sends the sender "Could you send a specific date and
      time ..." in their thread, and the manager gets nothing.
- [ ] `uv run pyright` is clean.

## Out of scope

- Booking after the manager's yes. Step 026 does that.
