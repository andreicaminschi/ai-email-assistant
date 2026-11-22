# Step 018 — Story: Urgent call

**Type:** Story · **Slice:** Slice 2 · **Depends on:** 017

## Goal

As the operator, an email with a deadline or an escalation gets the `URGENT` label next to
its own label, with the quote that proves it in the audit log.

## Context

- [retrieve-classify.md](../docs/retrieve-classify.md#what-the-urgent-call-sees): input,
  output, validator.
- [classify-tree.md](../docs/classify-tree.md#what-each-label-does-in-gmail): who gets
  `URGENT`.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/classify/urgent.py` | New. The urgent agent: `Date`, `Subject`, the priority-header hint, the follow-up body. Output `urgent` and `evidence`. The validator checks the evidence is in the email, and that `urgent` is false without evidence. |
| `src/email_agent/classify/models.py` | Add `urgent` and `evidence` to `Triage`. |
| `src/email_agent/classify/tree.py` | Run the urgent call after every label except `SPAM` and `UNCLASSIFIED`, after the times call for meetings. |
| `src/email_agent/dispatch.py` | Every handler except `SPAM`'s adds `URGENT` when the flag is set. |

## What to build

- The flag is a parameter of the handler. The tree never branches on it.
- This is generate-and-verify: the model proposes a quote, code checks it's really there.
- The audit entry's `urgent` column carries the flag.

## Acceptance criteria

- [ ] "Need approval for PTO today" from a colleague shows `TASK` and `URGENT` in Gmail.
- [ ] A sales pitch with `Importance: high` and no deadline shows no `URGENT`.
- [ ] A phishing email runs no urgent call, as the log shows.
- [ ] `uv run pyright` is clean.

## Out of scope

- The urgent wording in the forwards. Steps 022 and 025 do that.
- The invoice call. Step 021 adds it before the urgent call.
