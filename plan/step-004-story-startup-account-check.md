# Step 004 — Story: Startup account check

**Type:** Story · **Slice:** Foundation · **Depends on:** 002, 003

## Goal

As the operator, I start the agent and it proves both tokens work and belong to
`AGENT_EMAIL`, or it stops with one line saying which token is wrong.

## Context

- [gmail-oauth.md](../docs/gmail-oauth.md#startup-check): the check, in order, and every
  failure message.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/google_auth.py` | New. Loads one token file into credentials and refreshes the access token in memory. Raises a typed error for "missing" and "rejected". Never writes the file. |
| `src/email_agent/gmail.py` | New. Builds the Gmail service from its own token. First call: the account's email address from `users.getProfile`. |
| `src/email_agent/calendar.py` | New. Builds the Calendar service from its own token. First call: the primary calendar's ID from `calendarList.get`. |
| `src/email_agent/startup.py` | New. Runs the check in the documented order and returns both services. |
| `src/email_agent/__main__.py` | Run the check after config. On failure, log the documented line and exit 1. |

## What to build

- Gmail is checked fully before Calendar.
- Addresses match ignoring case.
- Each module loads only its own token file. Gmail code never opens the Calendar token.
- Failures print one line, with no stack trace.

## Acceptance criteria

- [ ] With both tokens valid, the log shows `Connection ready` and the agent exits 0.
- [ ] With `gmail_token` renamed, the log shows `Gmail token missing` and exit 1.
- [ ] With `AGENT_EMAIL` set to another address, the log shows `Gmail token is for another
      account` and exit 1.
- [ ] `uv run pyright` is clean.

## Out of scope

- Labels. Step 005 adds label setup after this check.
