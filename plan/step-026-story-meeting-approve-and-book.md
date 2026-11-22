# Step 026 — Story: Meeting booking or decline

**Type:** Story · **Slice:** Slice 5 · **Depends on:** 025, 030

## Goal

As the manager, my yes books the meeting on the calendar and invites the sender, and my
no sends the sender a polite decline. This closes slice 5.

## Context

- [calendar-scheduling.md](../docs/calendar-scheduling.md#the-event): event fields and the
  rerun guard.
- [approval.md](../docs/approval.md#handling-each-answer): what yes and no do.
- [email-templates.md](../docs/email-templates.md#meeting-declined): the decline.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/calendar.py` | Add insert event with a fixed ID and `sendUpdates=all`. A `409` returns "already created". |
| `src/email_agent/approval/flow.py` | `MEETING` answers: yes creates the event, no sends Meeting declined to the sender in the original thread. |

## What to build

- Event ID: the forward's thread ID. Title: the original subject. Attendee: the sender.
- Yes: audit action `create_event`. No: audit action `send_meeting_decline`.
- Both close the approval and the original email as `DONE`.
- Dev mode (`RUN_MODE=dev`): the event insert in `calendar.py` is the one switch. It
  calls no Calendar API and prints `DEV would book <start>-<end> <title>`. The decline
  goes through `sender.py`, so it's printed too.

## Acceptance criteria

- [ ] A yes to "Thu 26 Nov 10:00–10:30" creates the event, and the sender gets Google's
      invite.
- [ ] A no sends the sender "Unfortunately we can't make Thu 26 Nov 10:00–10:30.".
- [ ] Resetting the reply to `APPROVAL_REPLY` in SQLite and restarting creates no second
      event.
- [ ] In dev, a yes creates no event and the log shows `DEV would book ...`.
- [ ] `uv run pyright` is clean.

## Out of scope

- Checking the calendar for conflicts. Not in v1.
