from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models import Model

from email_agent.classify.label import SHARED_RULES
from email_agent.classify.models import UrgentResult
from email_agent.classify.times import is_quoted
from email_agent.llm import OUTPUT_RETRIES
from email_agent.message import Headers, ParsedEmail, read_header

URGENT_PROMPT = f"""\
You read one email and decide whether it is urgent.

Urgent means at least one of:
- A deadline on or before the second day after the email's Date header. "Today", "end of
  day", "tomorrow" and "ASAP" count.
- An explicit escalation, such as "URGENT", "escalating", or "production is down".

Not urgent:
- A deadline further away, or no deadline.
- Polite phrasing such as "when you get a chance".
- A priority note alone. Any sender can set the priority headers, so they need a deadline
  or escalation in the text too.

When urgent, set urgent to true and copy the words that show it as evidence, from the
subject or body.
When not, set urgent to false and leave evidence empty.

{SHARED_RULES}"""

type UrgentAgent = Agent[str, UrgentResult]


def check_urgent(context: RunContext[str], result: UrgentResult) -> UrgentResult:
    """
    @example
    check_urgent(ctx_with_text("Need this today"), UrgentResult(urgent=True, evidence="ASAP"))
    # → ModelRetry "evidence must be words copied exactly"
    """
    if not result.urgent:
        return UrgentResult(urgent=False)
    if not result.evidence:
        raise ModelRetry("urgent=true needs evidence. Copy the words, or set urgent to false.")
    if not is_quoted(result.evidence, context.deps):
        raise ModelRetry("evidence must be words copied exactly from the subject or body.")
    return result


def build_urgent_agent(model: Model) -> UrgentAgent:
    agent: UrgentAgent = Agent(
        model,
        deps_type=str,
        output_type=UrgentResult,
        system_prompt=URGENT_PROMPT,
        retries={"output": OUTPUT_RETRIES},
    )
    agent.output_validator(check_urgent)
    return agent


def has_priority_header(headers: Headers) -> bool:
    importance = read_header(headers, "Importance").strip().casefold()
    x_priority = read_header(headers, "X-Priority").strip()
    priority = read_header(headers, "Priority").strip().casefold()
    return importance == "high" or x_priority.startswith("1") or priority == "urgent"


def format_urgent_text(parsed: ParsedEmail) -> str:
    return "\n".join([parsed.subject, parsed.follow_up_body])


def format_urgent_input(parsed: ParsedEmail) -> str:
    lines = [f"Date: {parsed.date}", f"Subject: {parsed.subject}"]
    if has_priority_header(parsed.headers):
        lines.append("Priority: the sender marked this email high priority")
    lines.extend(["Body:", parsed.follow_up_body])
    return "\n".join(lines)
