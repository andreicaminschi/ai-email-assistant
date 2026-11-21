# AI Email & Calendar Assistant

An agent that watches a Gmail inbox, labels each email, and acts on it. It archives,
replies, flags, and books calendar events. Meeting bookings and urgent internal messages
wait for the manager's approval by email. The full spec is in
[docs/REQUIREMENTS.md](docs/REQUIREMENTS.md).

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

- The LLM only classifies. It gets no Gmail or Calendar tools, and code maps each label
  to its action.
- Only two cases need approval: a meeting request with proposed times, and an urgent
  message from an internal sender. Everything else runs on its own.
- Secrets live in `./secrets`, which is gitignored. They reach containers as compose file
  secrets at `/run/secrets/<name>`, never through env vars or image layers.
- There are two Google tokens, one for Gmail and one for Calendar. Each module loads only
  its own.
- Every container command is written for podman first, then docker.

## Project docs

| Doc | Covers |
| --- | --- |
| [REQUIREMENTS.md](docs/REQUIREMENTS.md) | Labels, required behaviour, the approval flow, constraints. |
| [gmail-oauth.md](docs/gmail-oauth.md) | The two OAuth tokens, scopes, the token script, the startup account check. |
| [containers.md](docs/containers.md) | Compose services, secrets, volumes, image build, run commands. |
| [containers-dev.md](docs/containers-dev.md) | The `claude -p` wrapper used in development. |

`tmp/` is gitignored scratch space. Nothing committed links into it.
