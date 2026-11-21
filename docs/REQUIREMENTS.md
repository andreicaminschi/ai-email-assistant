# AI Email & Calendar Assistant — Requirements

An autonomous agent that monitors a Gmail inbox, classifies incoming mail, and takes
action — archiving, replying, flagging, and booking calendar events — with human
approval gated on anything sent or scheduled on the user's behalf.

Derived from a take-home assessment brief for a senior Python / LLM role.

## Goal

Build an agent that:

- monitors a Gmail inbox
- classifies each incoming email and assigns a predefined label
- takes appropriate autonomous action, including calendar coordination and human
  approval where needed

## Evaluation conditions

- A dedicated Gmail account and Google Calendar are provisioned for the agent.
- The reviewer sends 20 emails to the inbox during a live run.
- The agent must handle them with no prior knowledge of their content.
- The calendar is pre-populated with existing events. The agent must plan around them.

## Labels

Every email gets exactly one primary label.

| Label | Meaning |
| --- | --- |
| `MEETING_REQUEST` | Calendar coordination needed |
| `TASK` | Action item for the manager |
| `INFO_ONLY` | FYI, no action needed |
| `SALES_OUTREACH` | Unsolicited vendor or sales contact |
| `MARKETING` | Newsletters, promotions, bulk mail |
| `SPAM` | Malicious, phishing, or junk mail |

`URGENT` is a modifier, not a primary label. It may be added to any primary label
except `SPAM`, and signals a deadline or an escalation.

At startup the agent creates every required Gmail label that doesn't exist yet,
including `Finance` for invoices. `SPAM` maps to Gmail's built-in Spam label.

## Required behaviour

| Incoming email | Label | Action | Approval |
| --- | --- | --- | --- |
| Newsletter from a known bulk sender | `MARKETING` | Archive | Automatic |
| Meeting request with proposed times | `MEETING_REQUEST`, times parsed | Create calendar event | Required, by email |
| Cold sales outreach | `SALES_OUTREACH` | Send polite decline, then archive | Automatic (configurable) |
| Urgent message from an internal sender | `URGENT` + `TASK`, flagged | Flag and notify the manager | Required |
| Invoice or receipt | `INFO_ONLY` | Archive under a `Finance` label | Automatic |
| Phishing or suspicious link | `SPAM` | Move to the Spam folder and log | Automatic |

Some emails warrant an automatic reply — a polite acknowledgement to a marketing
offer, a brief thank-you where appropriate. The agent decides when this is warranted.

Calendar events must respect existing availability and be scheduled sensibly.

A sender is internal when its domain is in `INTERNAL_DOMAINS` or its exact address is in
`INTERNAL_ADDRESSES`, and Gmail's own `Authentication-Results` header shows
`dmarc=pass`. Both lists are supplied at launch and never committed.

## Approval flow

Any calendar action, and any reply sent on behalf of the manager, requires email
confirmation before it executes:

1. The agent sends a summary of the intended action to the manager.
2. The manager replies `APPROVE` or `REJECT`.
3. The agent executes the action, or discards it.

The manager's reply arrives as an ordinary inbox email, so the agent must recognise it
as an approval, match it to the pending action, and act on it.

Only the two scenarios the table marks as requiring approval are gated: a meeting
request with proposed times, and an urgent message from an internal sender. Every other
action, sends included, runs automatically. Where the general rules disagree with the
table, the table wins.

## Non-functional requirements

- **Audit trail.** Every processed email produces a structured log entry recording the
  label, the action taken, and the outcome.
- **Error handling.** The agent fails gracefully and logs every failure.
- **Human in the loop.** Manager approval by email reply precedes any send or any
  calendar write.
- **Containerized.** The agent runs in a container. The Gmail account and its
  credentials are supplied through environment variables.
- Exposing the agent as an MCP server is optional.

## Technical constraints

- Python, using any open-source framework plus custom code.
- Any hosted LLM API. A locally deployed model is not acceptable.
- Gmail and Google Calendar integrations are required.
- The container must accept substituted LLM credentials at run time, so the provider
  must be configurable rather than hard-coded.

## Deliverables

1. Gmail and Google Calendar credentials for the account the agent runs against.
2. A containerized agent connected to that inbox, ready for a live run.
3. A README covering how to start and operate the agent.
