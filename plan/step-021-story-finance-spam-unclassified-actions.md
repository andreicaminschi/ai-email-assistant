# Step 021 — Story: Invoice call, spam and unclassified handlers

**Type:** Story · **Slice:** Slice 3 · **Depends on:** 020, 013, 030

## Goal

As the operator, invoices and receipts are filed under `Finance` and archived, other
`INFO_ONLY` mail stays in the inbox, phishing ends up in Spam, and unclassified mail is
left alone. This closes slice 3.

## Context

- [retrieve-classify.md](../docs/retrieve-classify.md#what-the-invoice-call-sees): the
  invoice call's input, output and validator.
- [classify-tree.md](../docs/classify-tree.md#step-order): the `INFO_ONLY`, `SPAM` and
  `UNCLASSIFIED` rows.
- `docs/llm-prompts.md`: the invoice prompt.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/classify/invoice.py` | New. The invoice agent: subject, attachment names, the follow-up body. Output `is_invoice` and `evidence`. The validator checks the evidence is in the email, and that `is_invoice` is false without evidence. |
| `src/email_agent/classify/models.py` | Add `is_invoice` and `invoice_evidence` to `Triage`. |
| `src/email_agent/classify/tree.py` | Run the invoice call after an external `INFO_ONLY`, before the urgent call. |
| `src/email_agent/dispatch.py` | `INFO_ONLY`: label (+ `URGENT`), and for an invoice add `Finance` and remove `INBOX`. `SPAM`: add `SPAM`, remove `INBOX`. `UNCLASSIFIED`: nothing. |

## What to build

- This is generate-and-verify, like the urgent call.
- Audit actions: `finance_and_archive`, `label_only`, `move_to_spam`,
  `none_unclassified`.
- Dev mode (`RUN_MODE=dev`): the invoice archive uses step 020's archive helper, so it
  adds `This is archived`. `SPAM` adds the `This is spam` label instead of `SPAM`, and
  `INBOX` stays.

## Acceptance criteria

- [ ] "Invoice #4512 for October" shows `INFO_ONLY` and `Finance` and leaves the inbox.
      The log shows the invoice evidence.
- [ ] "FYI, our office is closed Friday" shows `INFO_ONLY` only and stays in the inbox.
- [ ] A phishing test email lands in Spam.
- [ ] In dev, `ext-phishing` stays in the inbox with `This is spam`, and `ext-invoice`
      stays with `INFO_ONLY`, `Finance` and `This is archived`.
- [ ] An email that fits no label stays in the inbox with no label, and the audit line
      shows `none_unclassified`.
- [ ] `uv run pyright` is clean.

## Out of scope

- `TASK` and `MEETING_REQUEST` handlers. Slices 4 and 5 do those.
