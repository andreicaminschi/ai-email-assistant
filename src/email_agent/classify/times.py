from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models import Model

from email_agent.classify.label import SHARED_RULES
from email_agent.classify.models import TimesResult
from email_agent.llm import OUTPUT_RETRIES
from email_agent.message import ParsedEmail

TIMES_PROMPT = f"""\
You read one email that asks for a meeting, and extract the proposed date and time.

Date:
- Only an explicit date counts: a written day and month, such as "26 Nov" or "November
  26".
- Relative or vague words give no date: "tomorrow", "Thursday", "next week", "soon".
- When the year is missing, use the year of the email's Date header.
- When the email names several dates, return the first one.
- Return the date as YYYY-MM-DD, and copy the words that carry it as date_quote.

Time:
- Only a written clock time counts, such as "14:00" or "2pm". "Afternoon" or "after
  lunch" give no time.
- Return the time as HH:MM in 24-hour form, and copy the words that carry it as
  time_quote.
- Never return a time without a date.

When there is no explicit date, return everything empty.

{SHARED_RULES}"""

type TimesAgent = Agent[str, TimesResult]


def normalize_text(text: str) -> str:
    return " ".join(text.split()).casefold()


def is_quoted(quote: str | None, body: str) -> bool:
    return bool(quote) and normalize_text(quote or "") in normalize_text(body)


def check_times(context: RunContext[str], result: TimesResult) -> TimesResult:
    """
    @example
    check_times(ctx_with_body("Thu 26 Nov at 14:00"), TimesResult(meeting_time=time(14)))
    # → ModelRetry "a time needs a date"
    """
    body = context.deps
    if result.meeting_time is not None and result.meeting_date is None:
        raise ModelRetry("A time needs a date. Return no time, or add the date.")
    if result.meeting_date is not None and not is_quoted(result.date_quote, body):
        raise ModelRetry("date_quote must be words copied exactly from the email body.")
    if result.meeting_time is not None and not is_quoted(result.time_quote, body):
        raise ModelRetry("time_quote must be words copied exactly from the email body.")
    return result


def build_times_agent(model: Model) -> TimesAgent:
    agent: TimesAgent = Agent(
        model,
        deps_type=str,
        output_type=TimesResult,
        system_prompt=TIMES_PROMPT,
        retries={"output": OUTPUT_RETRIES},
    )
    agent.output_validator(check_times)
    return agent


def format_times_input(parsed: ParsedEmail) -> str:
    return "\n".join([f"Date: {parsed.date}", "Body:", parsed.follow_up_body])
