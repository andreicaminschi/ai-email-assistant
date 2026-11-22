# Step 017 — Story: Internal branch and times call

**Type:** Story · **Slice:** Slice 2 · **Depends on:** 016

## Goal

As the operator, internal senders are classified from their own small label set, and every
`MEETING_REQUEST` comes with its explicit date and optional time, or with none.

## Context

- [classify-tree.md](../docs/classify-tree.md): both trees.
- [retrieve-classify.md](../docs/retrieve-classify.md#what-the-times-call-sees): the times
  call's input, output and examples.
- `docs/llm-prompts.md`: the internal and times prompts.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/classify/label.py` | Add the internal-set label agent. |
| `src/email_agent/classify/times.py` | New. The times agent: input is the `Date` header and the follow-up body. Output is `meeting_date` and `meeting_time`, each with its quote. A validator retries when a quote isn't in the body, or a time comes without a date. |
| `src/email_agent/classify/models.py` | Add `meeting_date` and `meeting_time` to `Triage`. |
| `src/email_agent/classify/tree.py` | New. Walks the tree: branch from the internal flag, label call, times call for `MEETING_REQUEST`. Returns a new `Triage`. |
| `src/email_agent/process.py` | `CLASSIFYING` calls the tree instead of the label call directly. |

## What to build

- The tree is plain code. Each node is one narrow LLM question, which is conditional
  prompt chaining.
- Only a written day and month counts as a date. A missing year takes the `Date`
  header's year. The first date wins when there are several.
- Dates and times are in `TIME_ZONE` with no conversion.

## Acceptance criteria

- [ ] An internal sender's newsletter logs `UNCLASSIFIED`. The same email from an external
      sender logs `MARKETING`.
- [ ] "Can we meet Thu 26 Nov 2026?" logs `MEETING_REQUEST` with date 2026-11-26 and no
      time.
- [ ] "Thu 26 Nov at 14:00" logs date 2026-11-26 and time 14:00.
- [ ] "Can we meet next week?" logs `MEETING_REQUEST` with no date.
- [ ] `uv run pyright` is clean.

## Out of scope

- The urgent call. Step 018 adds it.
- Using the date. Step 025 does that.
