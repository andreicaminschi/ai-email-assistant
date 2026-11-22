import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic_ai.exceptions import AgentRunError, UnexpectedModelBehavior

from email_agent.approval.flow import ApprovalAnswer, build_approval_answer
from email_agent.approval.forward import send_forward
from email_agent.approval.reply_match import Answer, match_reply
from email_agent.audit import Action, write_audit_entry
from email_agent.checks import (
    SenderFlags,
    is_auto_reply,
    is_own_mail,
    read_dmarc,
    read_sender_flags,
)
from email_agent.classify.models import Triage
from email_agent.classify.tree import TreeAgents, classify_with_tree
from email_agent.calendar import book_meeting, has_event
from email_agent.config import RunMode, Settings
from email_agent.db import (
    ApprovalRow,
    EmailRow,
    State,
    close_approval,
    raise_attempts,
    read_approval,
    read_email,
    read_pending_approval,
    read_send,
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
    from googleapiclient._apis.calendar.v3 import CalendarResource  # pyright: ignore[reportMissingModuleSource]
    from googleapiclient._apis.gmail.v1 import GmailResource  # pyright: ignore[reportMissingModuleSource]

MAX_ATTEMPTS = 3
FORWARD_THREAD_MISSING = "forward thread missing"


@dataclass(frozen=True)
class ProcessedEmail:
    row: EmailRow
    flags: SenderFlags | None = None
    triage: Triage | None = None
    error: str | None = None
    review_detail: str | None = None
    answer: Answer | None = None


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


def is_approval_reply(
    connection: sqlite3.Connection, parsed: ParsedEmail, settings: Settings
) -> bool:
    """The manager, DMARC pass, in a forward's thread still awaiting approval."""
    return (
        parsed.from_address.casefold() == settings.manager_email.casefold()
        and read_dmarc(parsed.headers) == "pass"
        and read_pending_approval(connection, parsed.thread_id) is not None
    )


def ignore_reply(
    connection: sqlite3.Connection, row: EmailRow, answer: Answer, detail: str
) -> ProcessedEmail:
    write_audit_entry(
        connection, row.message_id, row.thread_id, Action.IGNORE_REPLY, State.DONE, detail
    )
    done = set_email_state(connection, row.message_id, State.DONE)
    return ProcessedEmail(row=done, answer=answer)


def finish_original_email(
    connection: sqlite3.Connection, approval: ApprovalRow, action: Action
) -> EmailRow | None:
    """Audit and DONE, once. None: the original row is gone."""
    original = read_email(connection, approval.message_id)
    if original is None or original.state is State.DONE:
        return original
    triage = read_saved_triage(original)
    urgent = None if triage is None else triage.urgent
    write_audit_entry(
        connection,
        original.message_id,
        original.thread_id,
        action,
        State.DONE,
        "",
        approval.kind,
        urgent,
    )
    return set_email_state(connection, original.message_id, State.DONE)


def is_answered_here(
    connection: sqlite3.Connection,
    calendar: CalendarResource,
    settings: Settings,
    row: EmailRow,
    approval_answer: ApprovalAnswer,
) -> bool:
    """A closed approval: did this reply act before a crash."""
    if approval_answer.outgoing is not None:
        template = approval_answer.outgoing.rendered.name
        return read_send(connection, row.message_id, template) is not None
    if approval_answer.event is None or settings.run_mode is RunMode.DEV:
        return False
    return has_event(calendar, approval_answer.event.event_id)


def answer_approval(
    connection: sqlite3.Connection,
    gmail: GmailResource,
    calendar: CalendarResource,
    settings: Settings,
    row: EmailRow,
    answer: Answer,
) -> ProcessedEmail:
    """Send or book, close the approval, then both emails DONE."""
    approval = read_approval(connection, row.thread_id)
    if approval is None:
        detail = "approval missing"
        return ProcessedEmail(row=review_email(connection, row, detail), review_detail=detail)
    approval_answer = build_approval_answer(approval, answer, settings.manager_email)
    if approval_answer is None:
        detail = "meeting times missing"
        return ProcessedEmail(row=review_email(connection, row, detail), review_detail=detail)
    closed = approval.state is not State.AWAITING_APPROVAL
    if closed and not is_answered_here(connection, calendar, settings, row, approval_answer):
        # Another reply closed it
        return ignore_reply(connection, row, answer, "approval already closed")
    if approval_answer.outgoing is not None:
        send_once(connection, gmail, settings, row.message_id, approval_answer.outgoing)
    if approval_answer.event is not None:
        book_meeting(calendar, settings.run_mode, settings.time_zone, approval_answer.event)
    if not closed:
        close_approval(connection, approval.forward_thread_id)
    finish_original_email(connection, approval, approval_answer.action)
    write_audit_entry(
        connection,
        row.message_id,
        row.thread_id,
        approval_answer.action,
        State.DONE,
        f"answer={answer}",
        approval.kind,
    )
    done = set_email_state(connection, row.message_id, State.DONE)
    return ProcessedEmail(row=done, answer=answer)


def read_approval_reply(
    connection: sqlite3.Connection,
    gmail: GmailResource,
    calendar: CalendarResource,
    settings: Settings,
    row: EmailRow,
    parsed: ParsedEmail,
) -> ProcessedEmail:
    """A yes or no answers the approval. No match is ignored and DONE."""
    replying = set_email_state(connection, row.message_id, State.APPROVAL_REPLY)
    answer = match_reply(parsed.follow_up_body)
    if answer is Answer.NO_MATCH:
        return ignore_reply(connection, replying, answer, "no decision word")
    return answer_approval(connection, gmail, calendar, settings, replying, answer)


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
        HandlerInput(
            parsed,
            triage,
            label_ids,
            settings.run_mode,
            settings.send_sales_decline,
            settings.manager_email,
            settings.meeting_default_time,
            settings.meeting_duration_minutes,
        )
    )


def run_handler_steps(
    connection: sqlite3.Connection,
    gmail: GmailResource,
    settings: Settings,
    row: EmailRow,
    parsed: ParsedEmail,
    triage: Triage,
    result: HandlerResult,
) -> EmailRow:
    """Labels, sends, forward, then archive. A lost forward thread gives NEEDS_REVIEW."""
    if result.add_label_ids or result.remove_label_ids:
        modify_labels(
            gmail, row.message_id, list(result.add_label_ids), list(result.remove_label_ids)
        )
    for outgoing in result.sends:
        send_once(connection, gmail, settings, row.message_id, outgoing)
    if result.forward is not None:
        approval = send_forward(connection, gmail, settings, parsed, result.forward)
        if approval is None:
            return review_email(connection, row, FORWARD_THREAD_MISSING, triage.label)
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
    stepped = run_handler_steps(connection, gmail, settings, row, parsed, triage, result)
    if stepped.state is State.NEEDS_REVIEW:
        return ProcessedEmail(
            row=stepped, flags=flags, triage=triage, review_detail=FORWARD_THREAD_MISSING
        )
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
    calendar: CalendarResource,
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
            if is_approval_reply(connection, parsed, settings):
                return read_approval_reply(connection, gmail, calendar, settings, row, parsed)
            return classify_and_dispatch(
                connection, gmail, settings, agents, label_ids, row, parsed
            )
        case State.APPROVAL_REPLY:
            return read_approval_reply(connection, gmail, calendar, settings, row, parsed)
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
