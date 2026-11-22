# Step 022 — Story: Task forward

**Type:** Story · **Slice:** Slice 4 · **Depends on:** 021, 030

## Goal

As the manager, every `TASK` reaches me as a forward with its own subject, saying who is
asking, whether it's urgent, and quoting their email, so I can answer yes or no.

## Context

- [approval.md](../docs/approval.md#the-forward): headers, body and the new thread.
- [email-templates.md](../docs/email-templates.md#approval-task): the template.
- [state-audit.md](../docs/state-audit.md#tables): the `approvals` columns.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/db.py` | Add the `approvals` table, read by forward thread, and save. |
| `src/email_agent/approval/__init__.py` | New, empty. Boilerplate. |
| `src/email_agent/approval/forward.py` | New. Renders the approval template and sends it through `sender.py` to `MANAGER_EMAIL`, outside any thread. Returns the forward's `threadId`. |
| `src/email_agent/dispatch.py` | `TASK`: labels first, then the forward. Internal `TASK` uses the same handler. |
| `src/email_agent/process.py` | Saves the approval of kind `TASK` under the forward's thread, saves `AWAITING_APPROVAL` on the email, writes the audit entry with action `forward_for_approval`. |

## What to build

- The forward has no `In-Reply-To` and no `threadId`, so Gmail starts a new thread.
- A second task in the same original thread gets its own forward and its own approval.
- `AWAITING_APPROVAL` emails aren't resumed by the poller. They wait for a reply.
- Dev mode (`RUN_MODE=dev`): the forward is really sent, because it goes to
  `MANAGER_EMAIL`. Sends to anyone else stay printed. Settled at the start of this step.

## Acceptance criteria

- [ ] "Need approval for PTO tomorrow" shows `TASK` in Gmail, and the manager receives
      "Approval needed: ..." in a new thread, quoting it.
- [ ] An urgent task's forward has the subject "Urgent approval needed: ..." and the
      urgent first line. A normal one doesn't.
- [ ] The `approvals` row holds the forward's thread ID and points to the original email.
- [ ] In dev, `int-task-pto-urgent` shows `TASK` and `URGENT`, and the manager gets
      "Urgent approval needed: ..." once. A dev restart doesn't send it again.
- [ ] `uv run pyright` is clean.

## Out of scope

- Reading the manager's reply. Step 023 does that.
