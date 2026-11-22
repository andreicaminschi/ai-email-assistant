# Step 024 — Story: Task answer to the sender

**Type:** Story · **Slice:** Slice 4 · **Depends on:** 023

## Goal

As the sender, I hear back in my own thread whether my request was approved or not. This
closes slice 4.

## Context

- [approval.md](../docs/approval.md#handling-each-answer): what yes and no do.
- [email-templates.md](../docs/email-templates.md): Task approved, Task rejected.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/approval/flow.py` | New. Takes the approval and the answer, returns the send and the next approval and email states. `TASK` only for now. |
| `src/email_agent/process.py` | A matched `APPROVAL_REPLY` runs the flow, applies the send through `sender.py`, saves states, writes the reply's and the original email's audit entries. |
| `src/email_agent/db.py` | Add closing an approval. |

## What to build

- Yes: Task approved to the sender in the original thread. Audit action
  `send_task_approved`.
- No: Task rejected to the sender in the original thread. Audit action
  `send_task_rejected`.
- Both close the approval and the original email as `DONE`.
- Sends are keyed by the reply's message ID, so a rerun of the reply sends nothing twice.

## Acceptance criteria

- [ ] Manager replies "Yes" and the sender receives "Your request was approved." in the
      original thread.
- [ ] Manager replies "No" and the sender receives "Your request was not approved.".
- [ ] A second "Yes" after the approval closed is classified as a new email and sends
      nothing to the sender.
- [ ] `uv run pyright` is clean.

## Out of scope

- Meeting answers. Step 026 adds them.
