import sqlite3
from dataclasses import dataclass

from email_agent.audit import Action, write_audit_entry
from email_agent.checks import SenderFlags, is_auto_reply, is_own_mail, read_sender_flags
from email_agent.config import Settings
from email_agent.db import EmailRow, State, raise_attempts, set_email_classifying, set_email_state
from email_agent.message import ParsedEmail


@dataclass(frozen=True)
class ProcessedEmail:
    row: EmailRow
    flags: SenderFlags | None


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


def process_new_email(
    connection: sqlite3.Connection, settings: Settings, row: EmailRow, parsed: ParsedEmail
) -> ProcessedEmail:
    reason = read_skip_reason(parsed, settings)
    if reason is not None:
        return skip_email(connection, row, reason)
    flags = read_sender_flags(parsed, settings)
    classifying = set_email_classifying(connection, row.message_id, flags.internal)
    return ProcessedEmail(row=classifying, flags=flags)


def process_email(
    connection: sqlite3.Connection, settings: Settings, row: EmailRow, parsed: ParsedEmail
) -> ProcessedEmail:
    attempted = raise_attempts(connection, row.message_id)
    if attempted.state is State.NEW:
        return process_new_email(connection, settings, attempted, parsed)
    return ProcessedEmail(row=attempted, flags=None)
