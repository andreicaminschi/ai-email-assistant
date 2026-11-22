from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models import Model

from email_agent.classify.label import SHARED_RULES
from email_agent.classify.models import InvoiceResult
from email_agent.classify.times import is_quoted
from email_agent.llm import OUTPUT_RETRIES
from email_agent.message import ParsedEmail

INVOICE_PROMPT = f"""\
You read one email and decide whether it is an invoice or a receipt.

Counts: a bill, an invoice, a receipt, or a payment confirmation for something bought.
Doesn't count: price lists, quotes, offers, pricing newsletters, or a mention of a payment
without the document itself.

When it counts, set is_invoice to true and copy the words that show it as evidence. The
quote may come from the subject, an attachment name or the body.
When it doesn't, set is_invoice to false and leave evidence empty.

{SHARED_RULES}"""

type InvoiceAgent = Agent[str, InvoiceResult]


def check_invoice(context: RunContext[str], result: InvoiceResult) -> InvoiceResult:
    """
    @example
    check_invoice(ctx_with_text("Invoice #4512"), InvoiceResult(is_invoice=True))
    # → ModelRetry "is_invoice=true needs evidence"
    """
    if not result.is_invoice:
        return InvoiceResult(is_invoice=False)
    if not result.evidence:
        raise ModelRetry("is_invoice=true needs evidence. Copy the words, or set it to false.")
    if not is_quoted(result.evidence, context.deps):
        raise ModelRetry(
            "evidence must be words copied exactly from the subject, an attachment name or "
            "the body."
        )
    return result


def build_invoice_agent(model: Model) -> InvoiceAgent:
    agent: InvoiceAgent = Agent(
        model,
        deps_type=str,
        output_type=InvoiceResult,
        system_prompt=INVOICE_PROMPT,
        retries={"output": OUTPUT_RETRIES},
    )
    agent.output_validator(check_invoice)
    return agent


def format_invoice_text(parsed: ParsedEmail) -> str:
    names = [attachment.name for attachment in parsed.attachments]
    return "\n".join([parsed.subject, *names, parsed.follow_up_body])


def format_invoice_input(parsed: ParsedEmail) -> str:
    names = [attachment.name for attachment in parsed.attachments]
    return "\n".join(
        [
            f"Subject: {parsed.subject}",
            f"Attachments: {', '.join(names) or 'none'}",
            "Body:",
            parsed.follow_up_body,
        ]
    )
