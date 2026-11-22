# Step 015 — Story: Label-only dispatch

**Type:** Story · **Slice:** Slice 1 · **Depends on:** 005, 014

## Goal

As the operator, every classified email shows its label in Gmail and gets an audit entry.
This closes slice 1: poll, parse, check, classify, label.

## Context

- [classify-tree.md](../docs/classify-tree.md#handlers): one handler per (sender, label)
  pair.
- [classify-tree.md](../docs/classify-tree.md#step-order): the full step order. This step
  builds its first step only.
- [state-audit.md](../docs/state-audit.md#audit-entry): actions `label_only` and
  `none_unclassified`.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/gmail.py` | Add modify labels: add and remove label IDs on one message. |
| `src/email_agent/dispatch.py` | New. A table of handlers keyed by (sender, label). Each handler takes the parsed email, its `Triage` and the label map, and returns the Gmail changes and the next state. For now every handler except `UNCLASSIFIED`'s adds its own label and ends in `DONE`. |
| `src/email_agent/process.py` | `CLASSIFIED` looks up the handler, applies its changes, writes the audit entry, saves `DONE`. |

## What to build

- Handlers decide, and `process.py` applies. Handlers make no API calls and write no
  audit entries.
- Internal `MEETING_REQUEST` and `TASK` map to the external handlers.
- `SPAM` adds Gmail's `SPAM` label for now. Step 021 completes the move to Spam.
- `UNCLASSIFIED`'s handler does nothing. The engine writes action `none_unclassified`.
- Every placeholder handler is replaced by a later step: 020, 021, 022 and 025.

## Acceptance criteria

- [ ] A newsletter shows the `MARKETING` label in Gmail and stays in the inbox for now.
- [ ] The log shows one JSON audit line with label, action `label_only`, outcome `DONE`.
- [ ] The `emails` row is `DONE`.
- [ ] `uv run pyright` is clean.

## Out of scope

- Sends, archiving, approvals.
- `URGENT`. Step 018 adds it.
