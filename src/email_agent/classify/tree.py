from dataclasses import dataclass

from pydantic_ai.models import Model

from email_agent.checks import SenderFlags
from email_agent.classify.label import (
    InternalLabelAgent,
    LabelAgent,
    build_internal_label_agent,
    build_label_agent,
    format_label_input,
)
from email_agent.classify.models import InternalLabelResult, Label, LabelResult, Triage
from email_agent.classify.times import TimesAgent, build_times_agent, format_times_input
from email_agent.llm import call_with_backoff
from email_agent.message import ParsedEmail


@dataclass(frozen=True)
class TreeAgents:
    external_label: LabelAgent
    internal_label: InternalLabelAgent
    times: TimesAgent


def build_tree_agents(model: Model) -> TreeAgents:
    return TreeAgents(
        external_label=build_label_agent(model),
        internal_label=build_internal_label_agent(model),
        times=build_times_agent(model),
    )


def run_label_call(
    agents: TreeAgents, parsed: ParsedEmail, flags: SenderFlags
) -> LabelResult | InternalLabelResult:
    prompt = format_label_input(parsed, flags)
    if flags.internal:
        return call_with_backoff(lambda: agents.internal_label.run_sync(prompt).output)
    return call_with_backoff(lambda: agents.external_label.run_sync(prompt).output)


def classify_with_tree(agents: TreeAgents, parsed: ParsedEmail, flags: SenderFlags) -> Triage:
    """
    @example
    classify_with_tree(agents, meeting_email, external_flags)
    # → Triage(label=MEETING_REQUEST, meeting_date=2026-11-26, meeting_time=14:00, ...)
    """
    labeled = run_label_call(agents, parsed, flags)
    if labeled.label is not Label.MEETING_REQUEST:
        return Triage(label=labeled.label, reason=labeled.reason)
    prompt = format_times_input(parsed)
    times = call_with_backoff(
        lambda: agents.times.run_sync(prompt, deps=parsed.follow_up_body).output
    )
    return Triage(
        label=labeled.label,
        reason=labeled.reason,
        meeting_date=times.meeting_date,
        date_quote=times.date_quote if times.meeting_date else None,
        meeting_time=times.meeting_time,
        time_quote=times.time_quote if times.meeting_time else None,
    )
