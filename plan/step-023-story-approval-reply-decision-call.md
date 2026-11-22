# Step 023 — Story: Approval reply word match

**Type:** Story · **Slice:** Slice 4 · **Depends on:** 022

## Goal

As the operator, the manager's reply in a forward's thread is recognised, never
classified, and read by its first word as yes, no, or no match.

## Context

- [retrieve-classify.md](../docs/retrieve-classify.md#one-email): the `APPROVAL_REPLY`
  split.
- [approval.md](../docs/approval.md#the-word-match): the word lists and examples.
- [approval.md](../docs/approval.md#messages-in-the-forwards-thread): the message routing
  table.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/process.py` | Before classification, route a reply from `MANAGER_EMAIL` with DMARC pass, in a thread whose approval is `AWAITING_APPROVAL`, to `APPROVAL_REPLY`. |
| `src/email_agent/approval/reply_match.py` | New. Pure function: takes the reply's newest text and returns yes, no, or no match, from the word lists. |
| `src/email_agent/db.py` | Add "pending approval for this thread". |

## What to build

- The first word is lowercased and stripped of trailing punctuation before the match.
- The word lists are fixed in code, as in [config.md](../docs/config.md#fixed-in-code).
- No match: the reply gets an audit entry with action `ignore_reply` and detail
  `no decision word`. The approval stays open.
- For now a yes or no is only logged. Step 024 acts on it.

## Acceptance criteria

- [ ] The manager replies "Yes, enjoy" to a task forward, and the log shows yes.
- [ ] "REJECTED." logs no.
- [ ] "Who is Jane?" logs `ignore_reply`, and the approval is still `AWAITING_APPROVAL`.
- [ ] The same "Yes" sent from a different address is classified as a new email instead.
- [ ] `uv run pyright` is clean.

## Out of scope

- Acting on the answer. Step 024 does that.
