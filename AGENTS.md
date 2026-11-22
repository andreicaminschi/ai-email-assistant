# AI Email & Calendar Assistant

An agent that watches a Gmail inbox, labels each email, and acts on it. It archives,
replies, flags, and books calendar events. Meeting requests and tasks wait for the
manager's yes or no by email. The full spec is in
[docs/REQUIREMENTS.md](docs/REQUIREMENTS.md).

This is a demo of LLM classification and extraction. It isn't a production or
enterprise system, so hardening stays out unless a doc asks for it.

## The pipeline

1. Poll Gmail for new mail.
2. Process the new emails one at a time.
3. Code decides whether the sender is internal or external.
4. One LLM call picks the email's label.
5. Smaller LLM calls extract the context that label's handler needs: urgent, meeting
   date and time, invoice or not.
6. The label and the extracted context go to the handler for that (sender, label) pair.
7. The handler acts in plain code. The engine writes the audit entry.

## Status

The flows are being designed. Each flow gets its own `docs/*.md` file with Mermaid
diagrams, and no application code is written yet.

## Tech stack

| Tech | Role |
| --- | --- |
| Python 3.14 | The app's language, on Astral's uv slim base image. |
| uv | Locks dependencies. Images build with `uv sync --frozen`. |
| Pydantic-AI | Calls the LLM and returns a validated `Triage` result. |
| Pydantic-Evals | Scores the classifier against hand-labeled emails. |
| Claude Sonnet 5.5 | The classifier model, `anthropic:claude-sonnet-5-5`. The model string and base URL come from `.env`. |
| `claude -p` wrapper | Development only. It serves an OpenAI-style endpoint backed by a Claude subscription. |
| `google-api-python-client` | Gmail and Google Calendar APIs. |
| `google-auth-oauthlib` | The host-side consent flow and in-memory token refresh. |
| SQLite | Processed email IDs and the last Gmail `historyId`, kept in a named volume. |
| Podman / Docker Compose | One `compose.yaml` that runs under both. |

New mail arrives by polling.

## Rules that shape the code

- The agent processes emails, one at a time. A label is what classification decides about
  an email. It's never a unit of work. Every action is a step taken on that email.
- Classification serves two purposes. The label is tagged on the email in Gmail to keep
  the inbox tidy, and it picks the actions the agent takes on that email.
- LLM calls only label and extract. They get no Gmail or Calendar tools.
- Each (internal or external, label) pair has its own handler. Internal `MEETING_REQUEST`
  and `TASK` reuse the external handlers. `UNCLASSIFIED`'s handler does nothing.
- Handlers don't log. The engine writes one audit entry after every handler.
- Only two labels wait for the manager: a `MEETING_REQUEST` with a date, and every
  `TASK`. A `TASK` is a request the manager can approve, such as "need approval for PTO
  tomorrow". Everything else runs on its own.
- The manager's answer is read by its first word, ignoring case. No LLM call reads it.
- Urgent is a flag passed to each handler. Every handler except `SPAM`'s adds the
  `URGENT` label when it's set.
- Secrets live in `./secrets`, which is gitignored. They reach containers as compose file
  secrets at `/run/secrets/<name>`, never through env vars or image layers.
- There are two Google tokens, one for Gmail and one for Calendar. Each module loads only
  its own.
- Every container command is written for podman first, then docker.

## Project docs

| Doc | Covers |
| --- | --- |
| [REQUIREMENTS.md](docs/REQUIREMENTS.md) | Labels, required behaviour, the approval flow, constraints. |
| [retrieve-classify.md](docs/retrieve-classify.md) | Polling, code checks before the LLM, the LLM calls' inputs, retries, sending without duplicates. |
| [classify-tree.md](docs/classify-tree.md) | The classification tree per sender branch, the handler per (sender, label) pair, and the step order per handler. |
| [approval.md](docs/approval.md) | The forward to the manager, the yes/no word match, what yes and no do. |
| [calendar-scheduling.md](docs/calendar-scheduling.md) | The meeting date and time to an event, the defaults, the rerun guard. |
| [state-audit.md](docs/state-audit.md) | The state catalog, SQLite tables, send states, the audit entry. |
| [email-templates.md](docs/email-templates.md) | The fixed-text template, placeholders and disclaimer for every email the agent sends. |
| [gmail-oauth.md](docs/gmail-oauth.md) | The two OAuth tokens, scopes, the token script, the startup account check, startup label setup. |
| [config.md](docs/config.md) | Every `.env` variable, every secret file, and the values fixed in code. |
| [containers.md](docs/containers.md) | Compose services, secrets, volumes, image build, run commands. |
| [containers-dev.md](docs/containers-dev.md) | The `claude -p` wrapper used in development. |

`tmp/` is gitignored scratch space. Nothing committed links into it.
