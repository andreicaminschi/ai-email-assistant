# Step 020 — Story: Marketing and sales handlers

**Type:** Story · **Slice:** Slice 3 · **Depends on:** 018, 019

## Goal

As the operator, a cold pitch gets a polite decline and leaves the inbox, and a marketing
email is archived without a reply. A restart never sends the same email twice.

## Context

- [classify-tree.md](../docs/classify-tree.md#step-order): the `MARKETING` and
  `SALES_OUTREACH` rows.
- [retrieve-classify.md](../docs/retrieve-classify.md#sending-without-duplicates): the
  send guard.
- [state-audit.md](../docs/state-audit.md#send-states): `SENDING` and `SENT`.
- [email-templates.md](../docs/email-templates.md#decisions): headers for every send.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/sender.py` | New. Send once: looks up the `sends` row for this message and template, generates a `Message-ID`, saves `SENDING`, sends, saves `SENT`. On `SENDING`, searches Sent for the ID first. Builds the MIME message from the template's subject and headers, with the thread ID only when the template replies in the sender's thread. Returns the sent message's `threadId`. |
| `src/email_agent/gmail.py` | Add send a raw message, in a thread or not, and search Sent by `rfc822msgid:`. |
| `src/email_agent/db.py` | Add the `sends` table. |
| `src/email_agent/dispatch.py` | External `MARKETING` and `SALES_OUTREACH` get their real handlers: labels, the decline when allowed, then remove `INBOX`. State `ARCHIVED`, then `DONE`. |

## What to build

- Order: labels, sends, archive. A crash leaves the email visible in the inbox.
- `MARKETING` never sends. `SALES_OUTREACH` skips the decline when
  `SEND_SALES_DECLINE=false`.
- Audit actions: `decline_and_archive`, or `archive` when no send went out.
- The email's state moves on only after every send in its step is `SENT`.

## Acceptance criteria

- [ ] A cold pitch from your own second address gets the decline in its thread, and the
      email leaves the inbox with the `SALES_OUTREACH` label.
- [ ] A newsletter is archived with the `MARKETING` label and no reply in Sent.
- [ ] Setting a `DONE` sales email back to `CLASSIFIED` in SQLite and restarting sends
      nothing new.
- [ ] `uv run pyright` is clean.

## Out of scope

- `INFO_ONLY`, spam and unclassified. Step 021 does those.
