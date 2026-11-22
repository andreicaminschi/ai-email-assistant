# Implementation plan

You get a running agent early, then one flow at a time added to it, each step small enough
to read in one sitting.

Choices made without you are listed in [assumptions.md](assumptions.md).

## How the steps work

- Each step is one file in this folder, written like a ticket: goal, context, files, what
  to build, acceptance, out of scope, dependencies.
- A **story** builds something. A **clarification** settles a question the next stories
  need before they can start.
- A step touches at most 5 files. Boilerplate, such as an empty `__init__.py` or template
  text files, doesn't count.
- Every step ends with a hand check and a clean type-check: `uv run pyright`. No test files.
- Every container command is given for podman first, then docker.
- The design lives in `docs/`. A step links the doc sections it implements and never
  repeats them.

## Slices

The plan builds a thin path through the whole agent first, then widens it.

```
Foundation   001-005  project, config, tokens, startup check, labels
Containers   006-008  app image, dev wrapper, compose
Slice 1      009-016  poll -> parse -> checks -> label call -> Gmail label -> retries
Slice 2      017-018  full classification tree: branches, times, urgent
Slice 3      019-021  autonomous handlers: templates, sends, archive, spam, invoice call
Slice 4      022-024  TASK approval: forward, yes/no word match, reply to sender
Slice 5      025-026  MEETING_REQUEST: forward or ask for a date, book or decline
Delivery     029      README
```

After slice 1 the agent labels every email in Gmail. Each later slice replaces the
placeholder handler for some labels with the real one. Steps 027 and 028 were removed
when the meeting flow was simplified, so the numbers skip them.

## Steps

| Step | Type | Title | Slice |
| --- | --- | --- | --- |
| [001](step-001-story-project-skeleton.md) | Story | Project skeleton | Foundation |
| [002](step-002-story-config.md) | Story | Config loading | Foundation |
| [003](step-003-story-token-script.md) | Story | Token script | Foundation |
| [004](step-004-story-startup-account-check.md) | Story | Startup account check | Foundation |
| [005](step-005-story-label-setup.md) | Story | Label setup | Foundation |
| [006](step-006-story-app-container.md) | Story | App container | Containers |
| [007](step-007-story-wrapper-endpoint.md) | Story | Wrapper endpoint | Containers |
| [008](step-008-story-wrapper-container.md) | Story | Wrapper container | Containers |
| [009](step-009-story-state-store.md) | Story | State store | Slice 1 |
| [010](step-010-story-polling.md) | Story | Polling | Slice 1 |
| [011](step-011-story-message-parsing.md) | Story | Message parsing | Slice 1 |
| [012](step-012-story-pre-llm-checks.md) | Story | Pre-LLM checks and audit | Slice 1 |
| [013](step-013-clarification-llm-prompts.md) | Clarification | LLM prompts and retry limits | Slice 1 |
| [014](step-014-story-label-call.md) | Story | Label call | Slice 1 |
| [015](step-015-story-label-only-dispatch.md) | Story | Label-only dispatch | Slice 1 |
| [016](step-016-story-retries-and-recovery.md) | Story | Retries and crash recovery | Slice 1 |
| [017](step-017-story-internal-branch-and-times-call.md) | Story | Internal branch and times call | Slice 2 |
| [018](step-018-story-urgent-call.md) | Story | Urgent call | Slice 2 |
| [019](step-019-story-templates.md) | Story | Email templates | Slice 3 |
| [020](step-020-story-marketing-and-sales-actions.md) | Story | Marketing and sales handlers | Slice 3 |
| [021](step-021-story-finance-spam-unclassified-actions.md) | Story | Invoice call, spam and unclassified handlers | Slice 3 |
| [022](step-022-story-task-approval-request.md) | Story | Task forward | Slice 4 |
| [023](step-023-story-approval-reply-decision-call.md) | Story | Approval reply word match | Slice 4 |
| [024](step-024-story-task-decision-handling.md) | Story | Task answer to the sender | Slice 4 |
| [025](step-025-story-meeting-approval-request.md) | Story | Meeting forward or date request | Slice 5 |
| [026](step-026-story-meeting-approve-and-book.md) | Story | Meeting booking or decline | Slice 5 |
| [029](step-029-story-readme.md) | Story | README | Delivery |

## Module map

Where each piece of the agent ends up. The step that creates a file is listed first.

| File | Holds | Steps |
| --- | --- | --- |
| `pyproject.toml`, `uv.lock` | Dependencies, the `wrapper` group, pyright | 001, 007 |
| `src/email_agent/__main__.py` | Startup order and the poll loop | 001, 002, 004, 005, 010 |
| `src/email_agent/config.py` | Settings from `.env` and secret files | 002 |
| `scripts/make_tokens.py` | Host-side OAuth consent | 003 |
| `src/email_agent/google_auth.py` | Token file to refreshed credentials | 004 |
| `src/email_agent/gmail.py` | Every Gmail API call | 004, 005, 010, 011, 015, 020 |
| `src/email_agent/calendar.py` | Every Calendar API call | 004, 026 |
| `src/email_agent/startup.py` | Account check and label setup | 004, 005 |
| `Containerfile`, `compose.yaml`, `.dockerignore` | Images and services | 006, 008 |
| `src/wrapper/` | Dev `claude -p` endpoint | 007 |
| `src/email_agent/db.py` | SQLite tables and queries | 009, 010, 012, 014, 020, 022-025 |
| `src/email_agent/poller.py` | One poll: history, full sync, new rows | 010, 016 |
| `src/email_agent/message.py`, `html_text.py` | Gmail message to a parsed email | 011 |
| `src/email_agent/checks.py` | Code checks before the LLM | 012 |
| `src/email_agent/process.py` | One email's state machine | 012, 014-017, 021-024 |
| `src/email_agent/audit.py` | Audit rows and stdout JSON lines | 012 |
| `docs/llm-prompts.md` | Prompt text and retry limits | 013 |
| `src/email_agent/llm.py` | Model and provider from config, backoff | 014, 016 |
| `src/email_agent/classify/` | Triage models, label, times, invoice and urgent calls, the tree | 014, 017, 018, 021 |
| `src/email_agent/dispatch.py` | One handler per (sender, label) pair | 015, 018, 020-022, 025 |
| `src/email_agent/templates.py`, `templates/` | Fixed email text | 019 |
| `src/email_agent/sender.py` | Send once, guarded by `sends` | 020 |
| `src/email_agent/approval/` | Forwards, the reply word match, yes/no handling | 022-026 |
| `README.md` | Start and operate the agent | 029 |
