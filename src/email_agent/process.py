import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

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
from email_agent.dispatch import HandlerInput, find_handler
from email_agent.gmail import modify_labels
from email_agent.message import ParsedEmail

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource  # pyright: ignore[reportMissingModuleSource]


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


def dispatch_email(
    connection: sqlite3.Connection,
    gmail: GmailResource,
    settings: Settings,
    label_ids: Mapping[str, str],
    classified: ProcessedEmail,
    parsed: ParsedEmail,
) -> ProcessedEmail:
    row = classified.row
    triage = classified.triage
    flags = classified.flags
    if triage is None or flags is None:
        return classified
    handler = find_handler(flags.internal, triage.label)
    result = handler(HandlerInput(parsed, triage, label_ids, settings.run_mode))
    if result.add_label_ids or result.remove_label_ids:
        modify_labels(
            gmail, row.message_id, list(result.add_label_ids), list(result.remove_label_ids)
        )
    write_audit_entry(
        connection, row.message_id, row.thread_id, result.action, result.state, "", triage.label
    )
    done = set_email_state(connection, row.message_id, result.state)
    return ProcessedEmail(row=done, flags=flags, triage=triage)


def process_new_email(
    connection: sqlite3.Connection,
    gmail: GmailResource,
    settings: Settings,
    label_agent: LabelAgent,
    label_ids: Mapping[str, str],
    row: EmailRow,
    parsed: ParsedEmail,
) -> ProcessedEmail:
    reason = read_skip_reason(parsed, settings)
    if reason is not None:
        return skip_email(connection, row, reason)
    flags = read_sender_flags(parsed, settings)
    classifying = set_email_classifying(connection, row.message_id, flags.internal)
    classified = classify_email(connection, label_agent, classifying, parsed, flags)
    return dispatch_email(connection, gmail, settings, label_ids, classified, parsed)


def process_email(
    connection: sqlite3.Connection,
    gmail: GmailResource,
    settings: Settings,
    label_agent: LabelAgent,
    label_ids: Mapping[str, str],
    row: EmailRow,
    parsed: ParsedEmail,
) -> ProcessedEmail:
    attempted = raise_attempts(connection, row.message_id)
    if attempted.state is State.NEW:
        return process_new_email(
            connection, gmail, settings, label_agent, label_ids, attempted, parsed
        )
    return ProcessedEmail(row=attempted, flags=None)
