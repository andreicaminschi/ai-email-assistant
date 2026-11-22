from dataclasses import dataclass

from pydantic_ai.models import Model

from email_agent.checks import SenderFlags
from email_agent.classify.invoice import (
    InvoiceAgent,
    build_invoice_agent,
    format_invoice_input,
    format_invoice_text,
)
from email_agent.classify.label import (
    InternalLabelAgent,
    LabelAgent,
    build_internal_label_agent,
    build_label_agent,
    format_label_input,
)
from email_agent.classify.models import InternalLabelResult, Label, LabelResult, Triage
from email_agent.classify.times import TimesAgent, build_times_agent, format_times_input
from email_agent.classify.urgent import (
    UrgentAgent,
    build_urgent_agent,
    format_urgent_input,
    format_urgent_text,
)
from email_agent.llm import call_with_backoff
from email_agent.message import ParsedEmail

NO_URGENT_CALL = frozenset({Label.SPAM, Label.UNCLASSIFIED})


@dataclass(frozen=True)
class TreeAgents:
    external_label: LabelAgent
    internal_label: InternalLabelAgent
    times: TimesAgent
    invoice: InvoiceAgent
    urgent: UrgentAgent


def build_tree_agents(model: Model) -> TreeAgents:
    return TreeAgents(
        external_label=build_label_agent(model),
        internal_label=build_internal_label_agent(model),
        times=build_times_agent(model),
        invoice=build_invoice_agent(model),
        urgent=build_urgent_agent(model),
    )


def run_label_call(
    agents: TreeAgents, parsed: ParsedEmail, flags: SenderFlags
) -> LabelResult | InternalLabelResult:
    prompt = format_label_input(parsed, flags)
    if flags.internal:
        return call_with_backoff(lambda: agents.internal_label.run_sync(prompt).output)
    return call_with_backoff(lambda: agents.external_label.run_sync(prompt).output)


def run_times_call(agents: TreeAgents, parsed: ParsedEmail, triage: Triage) -> Triage:
    prompt = format_times_input(parsed)
    times = call_with_backoff(
        lambda: agents.times.run_sync(prompt, deps=parsed.follow_up_body).output
    )
    return triage.model_copy(
        update={
            "meeting_date": times.meeting_date,
            "date_quote": times.date_quote if times.meeting_date else None,
            "meeting_time": times.meeting_time,
            "time_quote": times.time_quote if times.meeting_time else None,
        }
    )


def run_invoice_call(agents: TreeAgents, parsed: ParsedEmail, triage: Triage) -> Triage:
    prompt = format_invoice_input(parsed)
    text = format_invoice_text(parsed)
    invoice = call_with_backoff(lambda: agents.invoice.run_sync(prompt, deps=text).output)
    return triage.model_copy(
        update={"is_invoice": invoice.is_invoice, "invoice_evidence": invoice.evidence}
    )


def run_urgent_call(agents: TreeAgents, parsed: ParsedEmail, triage: Triage) -> Triage:
    prompt = format_urgent_input(parsed)
    text = format_urgent_text(parsed)
    urgent = call_with_backoff(lambda: agents.urgent.run_sync(prompt, deps=text).output)
    return triage.model_copy(update={"urgent": urgent.urgent, "evidence": urgent.evidence})


def classify_with_tree(agents: TreeAgents, parsed: ParsedEmail, flags: SenderFlags) -> Triage:
    """
    @example
    classify_with_tree(agents, invoice_email, external_flags)
    # → Triage(label=INFO_ONLY, is_invoice=True, invoice_evidence="Invoice #4512", urgent=False)
    """
    labeled = run_label_call(agents, parsed, flags)
    triage = Triage(label=labeled.label, reason=labeled.reason)
    if triage.label is Label.MEETING_REQUEST:
        triage = run_times_call(agents, parsed, triage)
    if triage.label is Label.INFO_ONLY and not flags.internal:
        triage = run_invoice_call(agents, parsed, triage)
    if triage.label in NO_URGENT_CALL:
        return triage
    return run_urgent_call(agents, parsed, triage)
