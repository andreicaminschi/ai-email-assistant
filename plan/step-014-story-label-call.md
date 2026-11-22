# Step 014 — Story: Label call

**Type:** Story · **Slice:** Slice 1 · **Depends on:** 008, 012, 013

## Goal

As the operator, every email that reaches `CLASSIFYING` gets a label and a reason from the
LLM, saved as a `Triage`, and the log shows both.

## Context

- [retrieve-classify.md](../docs/retrieve-classify.md#what-the-label-call-sees): the input.
- [retrieve-classify.md](../docs/retrieve-classify.md#triage-result): the result.
- [containers-dev.md](../docs/containers-dev.md#switching-app-to-the-wrapper): model
  switch.
- `docs/llm-prompts.md` from step 013: the prompt text.

## Files

| File | Change |
| --- | --- |
| `src/email_agent/llm.py` | New. Builds the Pydantic-AI model from `LLM_MODEL`, `LLM_BASE_URL` and the `llm_api_key` file. Anthropic and OpenAI-compatible providers. |
| `src/email_agent/classify/__init__.py` | New, empty. Boilerplate. |
| `src/email_agent/classify/models.py` | New. The `Triage` model and the label enum, `UNCLASSIFIED` included. |
| `src/email_agent/classify/label.py` | New. The external-set label agent. Builds its input from the parsed email and sender flags, returns label and reason. |
| `src/email_agent/process.py` | `CLASSIFYING` runs the label call, saves the `Triage` as JSON, moves to `CLASSIFIED`. |
| `src/email_agent/db.py` | Add saving the `triage` column. |

## What to build

- The model has no tools. It only returns the structured label result.
- Every email uses the external set for now. Step 017 adds the internal branch.
- `meeting_date`, `meeting_time`, `urgent` and `evidence` stay empty until steps 017 and
  018. `is_invoice` stays empty until step 021.
- A failed call leaves the email in `CLASSIFYING`. Step 016 adds retries and
  `NEEDS_REVIEW`.

## Acceptance criteria

- [ ] In dev (`podman compose --profile dev up --build`), a newsletter logs
      `CLASSIFIED MARKETING` with a reason.
- [ ] A cold sales pitch logs `SALES_OUTREACH`.
- [ ] Switching `.env` to the Anthropic API with a real key gives the same labels with no
      code change.
- [ ] `uv run pyright` is clean.

## Out of scope

- Acting on the label. Step 015 does that.
