import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic_ai.exceptions import AgentRunError, UnexpectedModelBehavior

from email_agent.audit import Action, write_audit_entry
from email_agent.checks import SenderFlags, is_auto_reply, is_own_mail, read_sender_flags
from email_agent.classify.models import Triage
from email_agent.classify.tree import TreeAgents, classify_with_tree
from email_agent.config import Settings
from email_agent.db import (
    EmailRow,
    State,
    raise_attempts,
    set_email_classified,
    set_email_classifying,
    set_email_state,
)
from email_agent.dispatch import HandlerInput, HandlerResult, find_handler
from email_agent.gmail import modify_labels
from email_agent.llm import is_transient
from email_agent.message import ParsedEmail
from email_agent.sender import send_once

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource  # pyright: ignore[reportMissingModuleSource]

MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class ProcessedEmail:
    row: EmailRow
    flags: SenderFlags | None = None
    triage: Triage | None = None
    error: str | None = None
    review_detail: str | None = None


def read_saved_triage(row: EmailRow) -> Triage | None:
    return None if row.triage is None else Triage.model_validate_json(row.triage)


def review_email(
    connection: sqlite3.Connection, row: EmailRow, detail: str, label: str = ""
) -> EmailRow:
    write_audit_entry(
        connection, row.message_id, row.thread_id, Action.NONE, State.NEEDS_REVIEW, detail, label
    )
    return set_email_state(connection, row.message_id, State.NEEDS_REVIEW)


def start_attempt(connection: sqlite3.Connection, row: EmailRow) -> ProcessedEmail:
    """
    @example
    start_attempt(connection, row)  # attempts 3 → 4 → NEEDS_REVIEW "attempts ran out"
    """
    attempted = raise_attempts(connection, row.message_id)
    if attempted.attempts <= MAX_ATTEMPTS:
        return ProcessedEmail(row=attempted)
    triage = read_saved_triage(attempted)
    label = "" if triage is None else triage.label
    detail = "attempts ran out"
    reviewed = review_email(connection, attempted, detail, label)
    return ProcessedEmail(row=reviewed, triage=triage, review_detail=detail)


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
    return ProcessedEmail(row=skipped)


def read_failure_detail(error: AgentRunError) -> str:
    if isinstance(error, UnexpectedModelBehavior) or is_transient(error):
        return "retries ran out"
    return "request rejected"


def classify_email(
    connection: sqlite3.Connection,
    agents: TreeAgents,
    row: EmailRow,
    parsed: ParsedEmail,
    flags: SenderFlags,
) -> ProcessedEmail:
    try:
        triage = classify_with_tree(agents, parsed, flags)
    except AgentRunError as error:
        detail = read_failure_detail(error)
        reviewed = review_email(connection, row, detail)
        return ProcessedEmail(row=reviewed, flags=flags, error=str(error), review_detail=detail)
    classified = set_email_classified(connection, row.message_id, triage.model_dump_json())
    return ProcessedEmail(row=classified, flags=flags, triage=triage)


def run_handler(
    settings: Settings,
    label_ids: Mapping[str, str],
    parsed: ParsedEmail,
    flags: SenderFlags,
    triage: Triage,
) -> HandlerResult:
    handler = find_handler(flags.internal, triage.label)
    return handler(
        HandlerInput(parsed, triage, label_ids, settings.run_mode, settings.send_sales_decline)
    )


def run_handler_steps(
    connection: sqlite3.Connection,
    gmail: GmailResource,
    settings: Settings,
    row: EmailRow,
    result: HandlerResult,
) -> EmailRow:
    """Labels, sends, then archive."""
    if result.add_label_ids or result.remove_label_ids:
        modify_labels(
            gmail, row.message_id, list(result.add_label_ids), list(result.remove_label_ids)
        )
    for outgoing in result.sends:
        send_once(connection, gmail, settings, row.message_id, outgoing)
    if result.archive is None:
        return row
    modify_labels(
        gmail,
        row.message_id,
        list(result.archive.add_label_ids),
        list(result.archive.remove_label_ids),
    )
    return set_email_state(connection, row.message_id, State.ARCHIVED)


def finish_email(
    connection: sqlite3.Connection, row: EmailRow, triage: Triage, result: HandlerResult
) -> EmailRow:
    write_audit_entry(
        connection,
        row.message_id,
        row.thread_id,
        result.action,
        result.state,
        "",
        triage.label,
        triage.urgent,
    )
    return set_email_state(connection, row.message_id, result.state)


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
    if row.state is not State.CLASSIFIED or triage is None or flags is None:
        return classified
    result = run_handler(settings, label_ids, parsed, flags, triage)
    stepped = run_handler_steps(connection, gmail, settings, row, result)
    done = finish_email(connection, stepped, triage, result)
    return ProcessedEmail(row=done, flags=flags, triage=triage)


def finish_archived_email(
    connection: sqlite3.Connection,
    settings: Settings,
    label_ids: Mapping[str, str],
    row: EmailRow,
    parsed: ParsedEmail,
) -> ProcessedEmail:
    """Writes the audit, then DONE."""
    flags = read_sender_flags(parsed, settings)
    triage = read_saved_triage(row)
    if triage is None:
        return ProcessedEmail(row=review_email(connection, row, "triage missing"), flags=flags)
    result = run_handler(settings, label_ids, parsed, flags, triage)
    done = finish_email(connection, row, triage, result)
    return ProcessedEmail(row=done, flags=flags, triage=triage)


def classify_and_dispatch(
    connection: sqlite3.Connection,
    gmail: GmailResource,
    settings: Settings,
    agents: TreeAgents,
    label_ids: Mapping[str, str],
    row: EmailRow,
    parsed: ParsedEmail,
) -> ProcessedEmail:
    flags = read_sender_flags(parsed, settings)
    classifying = set_email_classifying(connection, row.message_id, flags.internal)
    classified = classify_email(connection, agents, classifying, parsed, flags)
    return dispatch_email(connection, gmail, settings, label_ids, classified, parsed)


def process_email(
    connection: sqlite3.Connection,
    gmail: GmailResource,
    settings: Settings,
    agents: TreeAgents,
    label_ids: Mapping[str, str],
    row: EmailRow,
    parsed: ParsedEmail,
) -> ProcessedEmail:
    """Resumes from the saved state."""
    match row.state:
        case State.NEW:
            reason = read_skip_reason(parsed, settings)
            if reason is not None:
                return skip_email(connection, row, reason)
            return classify_and_dispatch(
                connection, gmail, settings, agents, label_ids, row, parsed
            )
        case State.CLASSIFYING:
            return classify_and_dispatch(
                connection, gmail, settings, agents, label_ids, row, parsed
            )
        case State.CLASSIFIED:
            saved = ProcessedEmail(
                row=row, flags=read_sender_flags(parsed, settings), triage=read_saved_triage(row)
            )
            return dispatch_email(connection, gmail, settings, label_ids, saved, parsed)
        case State.ARCHIVED:
            return finish_archived_email(connection, settings, label_ids, row, parsed)
        case _:
            return ProcessedEmail(row=row)
