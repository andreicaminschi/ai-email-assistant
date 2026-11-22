# Assumptions to check

These are things I decided on my own. Each row says where it lives, so you can change it
in one place.

## Doc updates

| Assumption | Where |
| --- | --- |
| A `TASK` gets `URGENT` straight away with its label, not after the manager's yes. | classify-tree.md, approval.md |
| The forward to the manager has its own subject, so Gmail starts a new thread. The pending approval is keyed by that thread, and the event ID is that thread ID. | approval.md, calendar-scheduling.md, state-audit.md |
| The times call returns the first explicit date when an email names several. A missing year takes the `Date` header's year. | retrieve-classify.md |
| A time range such as "2–4pm" books its start time, for the default length. | calendar-scheduling.md |
| The sender's answer to "Ask for a date and time" is classified as a new email, so a reply with a date gets forwarded like any meeting request. | classify-tree.md |
| A second gated email in the same thread gets its own forward. | approval.md |
| A manager reply gets its own audit entry, including an ignored one with action `ignore_reply`. | state-audit.md |
| The invoice call reads the subject, attachment names and body, and quotes its evidence like the urgent call. | retrieve-classify.md |
| A yes to a meeting sends no email of its own. Google's invite is the confirmation. | email-templates.md |
| The bulk flag stays, as a hint to the label call only. | retrieve-classify.md |
| Every column of every table, and the audit `action` values, from `none` through `ignore_reply`. | state-audit.md |
| The audit entry has two extra columns, `urgent` and `detail`, beyond label, action and outcome. | state-audit.md |
| The variables are named `LLM_MODEL`, `LLM_BASE_URL`, `MEETING_DEFAULT_TIME` and `MEETING_DURATION_MINUTES`. `TIME_ZONE`, `AGENT_EMAIL`, `MANAGER_EMAIL` and `LLM_MODEL` are required and have no default. | config.md |
| `.env.example` uses `Europe/Bucharest` as its sample zone. | .env.example |
| REQUIREMENTS.md stays as the original brief. approval.md notes where the project goes beyond it. | REQUIREMENTS.md |

## Plan choices

| Assumption | Step |
| --- | --- |
| The type-checker is pyright, in strict mode on `src`. | 001 |
| The package is `email_agent` under `src/`. The wrapper is a second package, `src/wrapper`, in the same uv project. | 001, 007 |
| Pydantic-AI is installed as `pydantic-ai-slim[anthropic,openai]`, not the full package. | 001 |
| Two new variables, `SECRETS_DIR` and `DATA_DIR`, let the agent run on the host before containers exist. | 002 |
| On the host, `.env` is loaded by `uv run --env-file .env`, with no dotenv dependency. | 002 |
| There's one `Containerfile` with `app` and `wrapper` targets, and only a `.dockerignore`, which podman also reads. | 006, 008 |
| The wrapper times out after 120 seconds. | 007 |
| HTML is turned into text with the standard library's parser, with no extra dependency. | 011 |
| Each SQLite table is created by the first step that needs it, not all of them up front. | 009, 012, 020, 022 |
| Prompt text and retry limits are the one clarification step. Its proposed defaults: 2 output retries, and backoff of 3 tries at 2, 4 and 8 seconds. | 013 |
| Templates are one `.txt` file each, and template names are an enum. | 019 |
| The poller doesn't resume emails waiting in `AWAITING_APPROVAL`. They wait for a reply. | 016, 022 |
| Hand checks need a second Gmail account to send test mail. Internal-sender checks need an address on a real domain, so DMARC can pass. | 012 onward |
| Every acceptance list ends with `uv run pyright`, and no step adds test files. | all |
