# Configuration

Every setting the agent reads. Plain values come from `.env`, which is gitignored.
[`.env.example`](../.env.example) is the committed copy with placeholder values. Secrets
are files in `./secrets`, covered in [containers.md](containers.md).

## `.env` variables

| Variable | Default | Example | Used by |
| --- | --- | --- | --- |
| `AGENT_EMAIL` | none, required | `agent@gmail.com` | Startup account check, skipping own mail. |
| `MANAGER_EMAIL` | none, required | `manager@gmail.com` | Forwards, matching the manager's replies. |
| `LLM_MODEL` | none, required | `anthropic:claude-sonnet-5-5` | Pydantic-AI model string. Dev: `openai:sonnet`. |
| `LLM_BASE_URL` | empty, the provider's default | `http://wrapper:8000/v1` | Pydantic-AI provider. Set only in dev. |
| `INTERNAL_DOMAINS` | empty | `acme.ai,acme.com` | Internal-sender check. |
| `INTERNAL_ADDRESSES` | empty | `ceo@gmail.com` | Internal-sender check. |
| `BULK_DOMAINS` | empty | `mailchimp.com` | Bulk flag. |
| `POLL_SECONDS` | `5` | `5` | Polling interval. |
| `TIME_ZONE` | none, required | `Europe/Bucharest` | The one IANA zone shared by sender, manager and calendar. |
| `MEETING_DEFAULT_TIME` | `10:00` | `10:00` | Meeting start when the email gives a date but no time. |
| `MEETING_DURATION_MINUTES` | `30` | `30` | Length of every booked meeting. |
| `SEND_SALES_DECLINE` | `true` | `false` | Turns the `SALES_OUTREACH` decline off. |
| `SECRETS_DIR` | `/run/secrets` | `./secrets` | Folder the secret files are read from. Set only on the host. |
| `DATA_DIR` | `/data` | `./data` | Folder for the SQLite file. Set only on the host. |

Lists are comma-separated and matched ignoring case. A missing required variable stops
startup with a log line naming it.

## Secrets

| File in `./secrets` | Mounted at | Read by |
| --- | --- | --- |
| `client_secret.json` | not mounted | Token script on the host |
| `gmail_token` | `/run/secrets/gmail_token` | Gmail module |
| `calendar_token` | `/run/secrets/calendar_token` | Calendar module |
| `llm_api_key` | `/run/secrets/llm_api_key` | Code that builds the Pydantic-AI provider. In dev it holds any dummy value. |
| `claude_token` | `/run/secrets/claude_token` | `wrapper` only |

The LLM key is read from its file and passed to the provider. It's never put in an env var.

## Fixed in code

| Value | Setting |
| --- | --- |
| Body cut | 1000 characters |
| Attempts per email | 3 |
| Approval "yes" words | `yes`, `approve`, `approved` |
| Approval "no" words | `no`, `reject`, `rejected` |
