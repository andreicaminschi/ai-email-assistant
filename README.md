# AI Email & Calendar Assistant

An agent that watches one Gmail inbox, labels each new email, and acts on it. It archives,
replies, moves spam, and books calendar events. Meeting requests and tasks wait for the
manager's yes or no by email. The full spec is in [REQUIREMENTS.md](docs/REQUIREMENTS.md).

## What it does

Code decides whether the sender is internal or external. One LLM call picks the label, and
smaller calls extract what the handler needs: urgent, meeting date and time, invoice or not.
The handler for that (sender, label) pair then acts in plain code.

| Sender | Label | What happens |
| --- | --- | --- |
| External | `MARKETING` | Labeled, archived. |
| External | `SALES_OUTREACH` | Labeled, a polite decline sent in its thread, archived. |
| External | `INFO_ONLY` | Labeled. An invoice or receipt also gets `Finance` and is archived. |
| External | `SPAM` | Moved to Spam. |
| Any | `MEETING_REQUEST` | Labeled. With a date, forwarded to the manager. Without one, the sender is asked for a date and time. |
| Any | `TASK` | Labeled, forwarded to the manager. |
| Any | `UNCLASSIFIED` | Nothing. |

An urgent email also gets the `URGENT` label. Internal senders only get `MEETING_REQUEST`,
`TASK` or `UNCLASSIFIED`. Details are in [classify-tree.md](docs/classify-tree.md).

## Setup

1. In Google Cloud Console, enable the Gmail and Google Calendar APIs. Create an OAuth
   client of type **Desktop** and save its JSON as `./secrets/client_secret.json`.
2. On the OAuth consent screen, keep **Testing** mode and add the agent's Gmail account as
   a test user.
3. Copy `.env.example` to `.env` and fill in `AGENT_EMAIL`, `MANAGER_EMAIL`, `RUN_MODE`
   and `INTERNAL_DOMAINS`. Every variable is in [config.md](docs/config.md).
4. Create both Google tokens. A browser opens twice; sign in as `AGENT_EMAIL` each time.

   ```powershell
   uv run --env-file .env scripts/make_tokens.py
   ```

5. Put the Anthropic API key in `./secrets/llm_api_key`. For dev, any dummy value works.
6. Dev only: run `claude setup-token` on the host and put the printed token in
   `./secrets/claude_token`.

`./secrets` is gitignored. Secrets reach the containers as compose file secrets, never as
env vars. Token details are in [gmail-oauth.md](docs/gmail-oauth.md).

## Run

`RUN_MODE=prod` runs every action. `RUN_MODE=dev` only labels, prints sends and bookings
instead of making them, and puts processed emails back to `NEW` on each start. Forwards
to the manager are really sent in both modes, so the approval loop can be tested.

Production, with `.env` set to `LLM_MODEL=anthropic:claude-sonnet-5-5` and no
`LLM_BASE_URL`:

```powershell
podman compose up -d
```

```powershell
docker compose up -d
```

Development, which also starts the `claude -p` wrapper. Set `LLM_MODEL=openai:sonnet` and
`LLM_BASE_URL=http://wrapper:8000/v1` in `.env`:

```powershell
podman compose --profile dev up -d
```

```powershell
docker compose --profile dev up -d
```

Follow the log. A good start prints `Connection ready`, then one line per email:

```powershell
podman compose logs -f app
```

```powershell
docker compose logs -f app
```

More on services, secrets and volumes is in [containers.md](docs/containers.md) and
[containers-dev.md](docs/containers-dev.md).

### Run on the host

The same agent runs without containers. Shell variables override `.env`, so these point it
at the local folders and the local wrapper. Start the wrapper in one terminal:

```powershell
$env:SECRETS_DIR = "./secrets"; uv run --group wrapper uvicorn wrapper.server:app --port 8000
```

Then the agent in another:

```powershell
$env:SECRETS_DIR = "./secrets"; $env:DATA_DIR = "./data"; $env:LLM_BASE_URL = "http://localhost:8000/v1"; uv run --env-file .env python -m email_agent
```

The wrapper needs Claude Code installed on the host.

### Load the sample emails

`samples/` holds one email per case. This imports all of them into the agent's inbox as
new, unread mail:

```powershell
uv run --env-file .env scripts/import_samples.py
```

## Operate

A forward arrives at `MANAGER_EMAIL` as a new thread. Reply in that thread. The agent reads
only the first word, ignoring case. Details are in [approval.md](docs/approval.md).

| Manager's first word | Task | Meeting |
| --- | --- | --- |
| `yes`, `approve`, `approved` | The sender gets "Your request was approved." in their thread. | The event is booked on the agent's calendar and the sender is invited. |
| `no`, `reject`, `rejected` | The sender gets "Your request was not approved." | The sender gets a decline naming the slot. |
| Anything else | Ignored. The approval keeps waiting. | Same. |

Only replies from `MANAGER_EMAIL` that pass DMARC count. Every sent text is in
[email-templates.md](docs/email-templates.md).

### Read the audit log

Each step prints one JSON line to stdout, in the log above. The same entries are kept in
the `audit` table of the SQLite file in the `agent-data` volume:

```powershell
podman compose exec app python -c "import sqlite3; [print(r) for r in sqlite3.connect('/data/agent.db').execute('select at, label, urgent, action, outcome, detail from audit order by id')]"
```

```powershell
docker compose exec app python -c "import sqlite3; [print(r) for r in sqlite3.connect('/data/agent.db').execute('select at, label, urgent, action, outcome, detail from audit order by id')]"
```

Every `action` and state is listed in [state-audit.md](docs/state-audit.md). Remove the
volume to start over with `podman compose down -v` or `docker compose down -v`.

## Swap the LLM

Change `LLM_MODEL` and `LLM_BASE_URL` in `.env` and the key in `./secrets/llm_api_key`.
`LLM_MODEL` is a Pydantic-AI model string, `provider:model`, such as
`anthropic:claude-sonnet-5-5`. No code changes. The prompts are in [llm-prompts.md](docs/llm-prompts.md).

## Limits

- Testing-mode OAuth tokens expire after 7 days. Rerun the token script to renew them.
- Meetings are booked only from an explicit date in the email. "Next week" gets a reply
  asking for a date.
- Booking doesn't check calendar availability.
- A manager reply without a decision word is ignored, with no reminder.
- Gmail rate limits aren't handled.
