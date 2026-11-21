# Gmail and Calendar connection (OAuth)

The agent reaches Gmail and Google Calendar with two OAuth tokens. A host-side script
creates them as files in `./secrets`, and startup checks both before any email is
touched. How the files reach the container is covered in [containers.md](containers.md).

## Decisions

| Topic | Decision |
| --- | --- |
| Tokens | Two tokens. One holds Gmail scopes only, one holds Calendar scopes only. Each module loads only its own. |
| OAuth client | A "Desktop" client in Google Cloud Console. Whoever does the live run creates their own. |
| Consent screen | Stays in Testing mode. The agent's Gmail account is added as a test user. |
| Token lifetime | Testing mode expires refresh tokens after 7 days. That's accepted for a demo. |
| Consent step | A token script runs on the host, opens a browser, and writes the token files. |
| Storage | All secrets live in `./secrets`, which is gitignored. |
| Refresh | Access tokens refresh in memory. The token files are never written back. |
| Account check | Startup confirms both tokens belong to `AGENT_EMAIL` from `.env`. |
| Revoked or expired token | Fixed by hand: rerun the token script. |

## Scopes

| Token | Scope | Covers |
| --- | --- | --- |
| Gmail | `gmail.modify` | Read, label, archive, move to Spam, send, create labels, read the profile. |
| Calendar | `calendar.readonly` | Free/busy, and the primary calendar's ID for the account check. |
| Calendar | `calendar.events` | Create events. |

`gmail.modify` can't permanently delete mail. The agent never needs to.

## Files

| File | Written by | Read by |
| --- | --- | --- |
| `./secrets/client_secret.json` | Downloaded from Cloud Console | Token script only |
| `./secrets/gmail_token.json` | Token script | Gmail module |
| `./secrets/calendar_token.json` | Token script | Calendar module |

Each token file holds the refresh token, `client_id` and `client_secret`. Only the token
script reads `client_secret.json`.

## Creating the tokens

The script runs the consent flow once per token. Each time, the runner signs in as the
agent's account and grants only that token's scopes.

```mermaid
sequenceDiagram
    actor Runner
    participant Script as Token script (host)
    participant Browser
    participant Google as Google OAuth
    participant Secrets as ./secrets

    Runner->>Script: run
    Script->>Secrets: read client_secret.json
    loop once per token: Gmail, then Calendar
        Script->>Browser: open consent URL with this token's scopes
        Runner->>Browser: sign in as AGENT_EMAIL, approve
        Browser->>Google: consent
        Google-->>Script: auth code via localhost redirect
        Script->>Google: exchange code
        Google-->>Script: refresh token + access token
        Script->>Secrets: write gmail_token.json or calendar_token.json
    end
```

## Startup check

Both tokens are checked before the agent reads any mail. A failed check logs which token
failed and why, then exits with a non-zero code. It prints no stack trace.

```mermaid
flowchart TD
    A[Start] --> B{Gmail token present?}
    B -- no --> X[Log: Gmail token missing. Exit]
    B -- yes --> C[Refresh access token]
    C -- fails --> Y[Log: Gmail token rejected, rerun token script. Exit]
    C -- ok --> D[users.getProfile]
    D --> E{emailAddress == AGENT_EMAIL?}
    E -- no --> Z[Log: Gmail token is for another account. Exit]
    E -- yes --> F{Calendar token present?}
    F -- no --> X2[Log: Calendar token missing. Exit]
    F -- yes --> G[Refresh access token]
    G -- fails --> Y2[Log: Calendar token rejected, rerun token script. Exit]
    G -- ok --> H[calendarList.get primary]
    H --> I{id == AGENT_EMAIL?}
    I -- no --> Z2[Log: Calendar token is for another account. Exit]
    I -- yes --> OK[Connection ready. Continue startup]
```

Matching ignores case.

## Replacing a token

When a token expires or is revoked, the agent can't recover on its own. Secrets are
refreshed by running the token script again, which overwrites both files in `./secrets`:

```powershell
uv run scripts/make_tokens.py
```
