# Step 031 — Story: Sample emails and import script

**Type:** Story · **Slice:** Dev · **Depends on:** 030

## Goal

As the operator, one command puts a sample email for every documented case into the
agent's inbox, without sending anything, so dev runs always have the same input.

## Context

- [classify-tree.md](../docs/classify-tree.md): the email tables per sender branch.
- [retrieve-classify.md](../docs/retrieve-classify.md): own mail, the bulk flag and the
  internal check.

## Files

| File | Change |
| --- | --- |
| `samples/*.eml` | New. One raw email per case. Text only. |
| `scripts/import_samples.py` | New. Reads `AGENT_EMAIL` and `SECRETS_DIR`, loads the Gmail token, and imports each sample with `messages.import` as unread inbox mail. |

## What to build

- Each import gets a fresh `Message-ID`, so a rerun adds a second copy.
- `{{AGENT_EMAIL}}` in a sample is replaced with `AGENT_EMAIL`.
- `neverMarkSpam` is set, so the phishing sample reaches the inbox.
- Internal samples come from `acme.com` with `Authentication-Results: mx.google.com;
  dmarc=pass`. They need `INTERNAL_DOMAINS=acme.com`.
- External senders use `*.example.com`, which can't receive mail.

## Acceptance criteria

- [ ] `uv run --env-file .env scripts/import_samples.py` prints one line per sample and
      `Imported <n> samples into <AGENT_EMAIL>`.
- [ ] The samples show in the inbox as unread, and the running agent logs each as `NEW`.
- [ ] `uv run pyright` is clean.

## Out of scope

- Deleting imported samples. Remove them in Gmail by hand.
