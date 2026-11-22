# Step 011 — Story: Message parsing

**Type:** Story · **Slice:** Slice 1 · **Depends on:** 010

## Goal

As the developer, each new email is turned into one parsed value holding everything the
checks and LLM calls need, and the log shows a short summary of it.

## Context

- [retrieve-classify.md](../docs/retrieve-classify.md#what-the-label-call-sees): headers,
  body, links, attachments.
- [retrieve-classify.md](../docs/retrieve-classify.md#what-the-times-call-sees): the
  follow-up body with links replaced.
- [email-templates.md](../docs/email-templates.md#placeholders): sender name and address.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/gmail.py` | Add get one message in `full` format. |
| `src/email_agent/html_text.py` | New. Uses the standard library's HTML parser to turn HTML into text, collecting each `<a href>` as link text plus domain. A second mode replaces each link with its text. |
| `src/email_agent/message.py` | New. A frozen `ParsedEmail`: Gmail IDs, `From` name and address, `To`, `Reply-To`, `Subject`, `Date`, `Message-ID`, every header needed by the checks, the label-call body, the follow-up body, the links list, attachment names and sizes. |
| `src/email_agent/__main__.py` | Parse each new email and log its sender, subject, body length and link count. |

## What to build

- The full email is fetched by a second call after its `NEW` row is saved. The poller's
  metadata call stays.
- `text/plain` is preferred. With only `text/html`, the HTML is converted. The label-call
  body shows a link as `here (cal.com)`, the follow-up body as `here`.
- Both bodies are cut at 1000 characters after building. The links list covers the whole
  body.
- The links list reads the HTML part whenever there is one. With no HTML part, each
  plain-text URL gives its domain only.
- Header lookup ignores case. Repeated headers, like `Authentication-Results`, keep every
  value in order.

## Acceptance criteria

- [ ] A plain-text email logs its sender, subject and body length.
- [ ] An HTML newsletter logs a link count above zero, and its follow-up body shows link
      text, not URLs.
- [ ] An email with a PDF attachment lists its file name and size.
- [ ] `uv run pyright` is clean.

## Out of scope

- Deciding anything from the parsed values. Step 012 starts the checks.
