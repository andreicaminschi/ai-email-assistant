# Step 013 — Clarification: LLM prompts and retry limits

**Type:** Clarification · **Slice:** Slice 1 · **Depends on:** none · **Blocks:** 014,
016, 017, 018, 021

## Goal

Settle what each LLM call is told and how many times it may retry, so the call stories
build to a fixed text instead of inventing prompts as they go.

## Context

The docs define each call's inputs, outputs and validators, but no prompt text and no
retry counts.

- [retrieve-classify.md](../docs/retrieve-classify.md#classification-tree): label, times,
  invoice and urgent calls.
- [classify-tree.md](../docs/classify-tree.md#what-each-label-means): the `TASK` and
  `UNCLASSIFIED` definitions.

## Questions to settle

| Question | Why it matters | Proposed default |
| --- | --- | --- |
| How is each label defined to the model? | The definitions are the classifier. "Invoice" versus "spam" and "sales" versus "marketing" depend on them. | One line per label, taken from the requirements table, plus one example email per label. |
| How is `TASK` told apart from `UNCLASSIFIED`? | Only approvable requests are `TASK`. "Need that velocity report" must not become one. | Define `TASK` as "asks the manager to approve or reject something", with the PTO and velocity examples. |
| Does the internal set's prompt differ from the external one? | Internal mail has only `TASK`, `MEETING_REQUEST` and `UNCLASSIFIED`. | Same structure, smaller label list. |
| What counts as an explicit date for the times call? | Only explicit dates are booked. "Thursday" or "next week" must give no date. | A written day and month. Relative words give no date. |
| What counts as an invoice or receipt? | Only those get `Finance`. A newsletter about pricing must not. | A bill, invoice, receipt or payment confirmation for something bought, quoted from the email. |
| How is "urgent" defined? | Too loose and every newsletter is urgent. | A deadline within a few days, or an explicit escalation, quoted from the text. |
| How many output retries per call? | Each retry costs a call and adds latency. | 2. |
| What backoff for API failures? | It decides how long one failing email blocks the queue. | 3 tries, waiting 2, 4 and 8 seconds. |

## Outcome

A new `docs/llm-prompts.md` with each call's system prompt text and the retry and backoff
values. `config.md`'s "Fixed in code" table gets the retry and backoff values.

## Out of scope

- Model choice. It stays `LLM_MODEL` from `.env`.
- The manager's reply. It's read by word match, with no prompt.
