# Step 012 — Story: Pre-LLM checks and audit

**Type:** Story · **Slice:** Slice 1 · **Depends on:** 011

## Goal

As the operator, the agent skips its own mail and automatic replies, works out each
sender's flags in code, and leaves one audit line per skipped email in the log and the
database.

## Context

- [retrieve-classify.md](../docs/retrieve-classify.md#one-email): the order of checks.
- [REQUIREMENTS.md](../docs/REQUIREMENTS.md#required-behaviour): internal senders and DMARC.
- [state-audit.md](../docs/state-audit.md#audit-entry): audit columns and values.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/checks.py` | New. Pure functions: is own mail, is automatic reply, DMARC result from the `Authentication-Results` header written by `mx.google.com`, is internal, is bulk. Returns a frozen `SenderFlags`. |
| `src/email_agent/process.py` | New. Processes one email from its saved state. Raises the attempt count, then routes `NEW` to `SKIPPED` or `CLASSIFYING`. |
| `src/email_agent/audit.py` | New. Writes one audit row and prints the same entry as one JSON line on stdout. |
| `src/email_agent/db.py` | Add the `audit` table and the `attempts` and `internal` updates. |
| `src/email_agent/__main__.py` | Hand each new email to `process.py` in arrival order, after its parse lines print. |

## What to build

- Only the `Authentication-Results` header whose first token is `mx.google.com` counts.
  A sender's own copy of the header is ignored.
- Internal means the domain is in `INTERNAL_DOMAINS` or the address is in
  `INTERNAL_ADDRESSES`, and DMARC is `pass`.
- `SKIPPED` writes an audit entry with action `none` and detail `own mail` or
  `auto-reply`.
- `CLASSIFYING` is the end of the line for now. The email waits there until step 014.

## Acceptance criteria

- [ ] An email sent from `AGENT_EMAIL` to itself prints a JSON audit line with outcome
      `SKIPPED` and detail `own mail`.
- [ ] A Gmail vacation reply is `SKIPPED` with detail `auto-reply`.
- [ ] An email from an address on `INTERNAL_ADDRESSES` logs `internal=true`. The same
      address not on the list logs `internal=false`.
- [ ] `uv run pyright` is clean.

## Out of scope

- Routing the manager's replies to pending approvals. Step 023 adds it.
