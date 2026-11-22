# Calendar scheduling

How the agent turns a meeting request's date and time into an event on its own calendar.
When the event gets created, after the manager's yes, is in
[approval.md](approval.md#handling-each-answer).

## Decisions

| Topic | Decision |
| --- | --- |
| Calendar | The agent account's own Google Calendar, the one the brief pre-populates. No other calendar is read or written, and no extra token is needed. |
| Accounts | `MANAGER_EMAIL` and `AGENT_EMAIL` are different accounts. |
| Input | The times call's `meeting_date` and optional `meeting_time`. Only explicit dates count, as in [retrieve-classify.md](retrieve-classify.md#what-the-times-call-sees). |
| Start | `meeting_time` when the email gives one. Otherwise `MEETING_DEFAULT_TIME` from `.env`, default `10:00`. |
| Length | Always `MEETING_DURATION_MINUTES` from `.env`, default `30`. |
| Time zone | One zone for everyone: the sender, the manager and the calendar. It's `TIME_ZONE` in `.env`. Times are never converted. |
| Availability | Not checked in v1. The event is booked even when the slot is busy. |
| Event | Title from the subject, no description, the sender invited, Google emails the invite. |
| Rerun guard | A fixed event ID. A second insert returns `409`, which counts as done. |

## Running example

Jane writes on Mon 23 Nov 2026, and the manager says yes.

| Jane writes | `meeting_date` | `meeting_time` | Event |
| --- | --- | --- | --- |
| "Can we meet Thu 26 Nov 2026?" | 2026-11-26 | empty | Thu 26 Nov 10:00–10:30 |
| "Thu 26 Nov at 14:00" | 2026-11-26 | 14:00 | Thu 26 Nov 14:00–14:30 |
| "26 Nov, 2–4pm" | 2026-11-26 | 14:00 | Thu 26 Nov 14:00–14:30 |
| "Thursday afternoon" | empty | empty | None. Jane is asked for a date and time before the manager sees it. |

## The event

| Field | Value |
| --- | --- |
| `id` | The forward's `threadId` F, such as `18c2f0a1b2c3d4e5` |
| `summary` | The original subject, without `Re:` |
| `start` | `meeting_date` at `meeting_time`, or at `MEETING_DEFAULT_TIME` |
| `end` | `start` plus `MEETING_DURATION_MINUTES` |
| `attendees` | The original sender |
| `sendUpdates` | `all`, so Google emails the sender the invite |

Each forward gets its own F, so each approved meeting gets its own ID. A rerun builds the
same ID, so the second insert returns `409 Conflict` and the agent treats the event as
created.

The `threadId` is hex, which is valid in Google's base32hex ID alphabet, so the ID always
passes Google's format check.

| Case | Insert result | Agent does |
| --- | --- | --- |
| First run | `200` | Closes the approval as `DONE` |
| Crash after the insert, then a rerun | `409` | Closes the approval as `DONE` |
