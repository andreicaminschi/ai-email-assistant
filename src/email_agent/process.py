import sqlite3
from dataclasses import dataclass

from pydantic_ai.exceptions import AgentRunError

from email_agent.audit import Action, write_audit_entry
from email_agent.checks import SenderFlags, is_auto_reply, is_own_mail, read_sender_flags
from email_agent.classify.label import LabelAgent, run_label_call
from email_agent.classify.models import Triage
from email_agent.config import Settings
from email_agent.db import (
    EmailRow,
    State,
    raise_attempts,
    set_email_classified,
    set_email_classifying,
    set_email_state,
)
from email_agent.message import ParsedEmail


@dataclass(frozen=True)
class ProcessedEmail:
    row: EmailRow
    flags: SenderFlags | None
    triage: Triage | None = None
    error: str | None = None


def read_skip_reason(parsed: ParsedEmail, settings: Settings) -> str | None:
    if is_own_mail(parsed, settings.agent_email):
        return "own mail"
    if is_auto_reply(parsed.headers):
        return "auto-reply"
    return None


def skip_email(connection: sqlite3.Connection, row: EmailRow, reason: str) -> ProcessedEmail:
    skipped = set_email_state(connection, row.message_id, State.SKIPPED)
    write_audit_entry(
        connection, row.message_id, row.thread_id, Action.NONE, State.SKIPPED, reason
    )
    return ProcessedEmail(row=skipped, flags=None)


def classify_email(
    connection: sqlite3.Connection,
    label_agent: LabelAgent,
    row: EmailRow,
    parsed: ParsedEmail,
    flags: SenderFlags,
) -> ProcessedEmail:
    try:
        result = run_label_call(label_agent, parsed, flags)
    except AgentRunError as error:
        return ProcessedEmail(row=row, flags=flags, error=str(error))
    triage = Triage(label=result.label, reason=result.reason)
    classified = set_email_classified(connection, row.message_id, triage.model_dump_json())
    return ProcessedEmail(row=classified, flags=flags, triage=triage)


def process_new_email(
    connection: sqlite3.Connection,
    settings: Settings,
    label_agent: LabelAgent,
    row: EmailRow,
    parsed: ParsedEmail,
) -> ProcessedEmail:
    reason = read_skip_reason(parsed, settings)
    if reason is not None:
        return skip_email(connection, row, reason)
    flags = read_sender_flags(parsed, settings)
    classifying = set_email_classifying(connection, row.message_id, flags.internal)
    return classify_email(connection, label_agent, classifying, parsed, flags)


def process_email(
    connection: sqlite3.Connection,
    settings: Settings,
    label_agent: LabelAgent,
    row: EmailRow,
    parsed: ParsedEmail,
) -> ProcessedEmail:
    attempted = raise_attempts(connection, row.message_id)
    if attempted.state is State.NEW:
        return process_new_email(connection, settings, label_agent, attempted, parsed)
    return ProcessedEmail(row=attempted, flags=None)
