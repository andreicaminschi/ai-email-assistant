# Step 003 — Story: Token script

**Type:** Story · **Slice:** Foundation · **Depends on:** 001

## Goal

As the person doing the live run, I run one script on my machine, approve two consent
screens, and end up with a Gmail token and a Calendar token in `./secrets`.

## Context

- [gmail-oauth.md](../docs/gmail-oauth.md#creating-the-tokens): the consent flow.
- [gmail-oauth.md](../docs/gmail-oauth.md#scopes): which scopes each token gets.
- [gmail-oauth.md](../docs/gmail-oauth.md#files): what each file holds.

## Files

| File | Change |
| --- | --- |
| `scripts/make_tokens.py` | New. Reads `./secrets/client_secret.json`, runs the installed-app flow once per token, writes `gmail_token` and `calendar_token`. |

## What to build

- Gmail token: scope `gmail.modify` only.
- Calendar token: scopes `calendar.readonly` and `calendar.events` only.
- Each run opens the browser with a localhost redirect, then writes the authorized-user
  JSON: refresh token, `client_id`, `client_secret`.
- The script prints which account to sign in as before each consent, and which file it
  wrote after.
- A missing `client_secret.json` prints where to download it and exits 1.

## Acceptance criteria

- [ ] `uv run scripts/make_tokens.py` opens two consent screens in turn.
- [ ] Both files exist in `./secrets`, and each holds a `refresh_token`.
- [ ] The Gmail file lists only the Gmail scope, the Calendar file only Calendar scopes.
- [ ] `uv run pyright` is clean.

## Out of scope

- Checking which account the tokens belong to. Step 004 does that at agent startup.
