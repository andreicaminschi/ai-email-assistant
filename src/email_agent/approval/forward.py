import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING

from email_agent.config import Settings
from email_agent.db import ApprovalKind, ApprovalRow, State, save_approval
from email_agent.message import ParsedEmail
from email_agent.sender import OutgoingEmail, send_once
from email_agent.templates import (
    TemplateName,
    format_quoted_text,
    format_slot,
    read_sender_name,
    render_template,
    strip_reply_prefix,
)

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource  # pyright: ignore[reportMissingModuleSource]


@dataclass(frozen=True)
class ApprovalForward:
    kind: ApprovalKind
    outgoing: OutgoingEmail
    sender_email: str
    sender_name: str
    original_subject: str
    meeting_start: str | None = None
    meeting_end: str | None = None


@dataclass(frozen=True)
class MeetingSlot:
    """Local times in TIME_ZONE, never converted."""

    start: datetime
    end: datetime
    text: str


def read_meeting_slot(
    day: date, meeting_time: time | None, default_time: time, duration_minutes: int
) -> MeetingSlot:
    """
    @example
    read_meeting_slot(date(2026, 11, 26), None, time(10, 0), 30).text
    # → "Thu 26 Nov 10:00–10:30"
    """
    start_time = meeting_time or default_time
    start = datetime.combine(day, start_time)
    end = start + timedelta(minutes=duration_minutes)
    return MeetingSlot(start, end, format_slot(day, start_time, duration_minutes))


def build_approval_forward(
    parsed: ParsedEmail,
    template: TemplateName,
    urgent: bool,
    manager_email: str,
    slot: MeetingSlot | None,
) -> ApprovalForward:
    sender_name = read_sender_name(parsed.from_name, parsed.from_address)
    original_subject = strip_reply_prefix(parsed.subject)
    values = {
        "sender_name": sender_name,
        "sender_email": parsed.from_address,
        "quoted_text": format_quoted_text(parsed.follow_up_body),
        "original_subject": original_subject,
        "slot": "" if slot is None else slot.text,
    }
    rendered = render_template(template, values, urgent)
    # New thread: no threadId
    outgoing = OutgoingEmail(to=manager_email, rendered=rendered, thread_id=None, in_reply_to="")
    answer_address = parsed.reply_to or parsed.from_address
    if slot is None:
        return ApprovalForward(
            ApprovalKind.TASK, outgoing, answer_address, sender_name, original_subject
        )
    return ApprovalForward(
        ApprovalKind.MEETING,
        outgoing,
        answer_address,
        sender_name,
        original_subject,
        slot.start.isoformat(timespec="minutes"),
        slot.end.isoformat(timespec="minutes"),
    )


def build_task_forward(parsed: ParsedEmail, urgent: bool, manager_email: str) -> ApprovalForward:
    """
    @example
    build_task_forward(pto_email, True, "boss@x.com").outgoing.rendered.subject
    # → "Urgent approval needed: PTO"
    """
    return build_approval_forward(parsed, TemplateName.APPROVAL_TASK, urgent, manager_email, None)


def build_meeting_forward(
    parsed: ParsedEmail, urgent: bool, manager_email: str, slot: MeetingSlot
) -> ApprovalForward:
    """
    @example
    build_meeting_forward(tom_email, False, "boss@x.com", slot).meeting_start
    # → "2026-11-26T14:00"
    """
    return build_approval_forward(
        parsed, TemplateName.APPROVAL_MEETING, urgent, manager_email, slot
    )


def send_forward(
    connection: sqlite3.Connection,
    gmail: GmailResource,
    settings: Settings,
    parsed: ParsedEmail,
    forward: ApprovalForward,
) -> ApprovalRow | None:
    """Sends once, then saves the approval under the forward's thread. None: thread not found."""
    forward_thread_id = send_once(connection, gmail, settings, parsed.message_id, forward.outgoing)
    if not forward_thread_id:
        return None
    approval = ApprovalRow(
        forward_thread_id=forward_thread_id,
        message_id=parsed.message_id,
        original_thread_id=parsed.thread_id,
        kind=forward.kind,
        state=State.AWAITING_APPROVAL,
        sender_email=forward.sender_email,
        sender_name=forward.sender_name,
        original_subject=forward.original_subject,
        meeting_start=forward.meeting_start,
        meeting_end=forward.meeting_end,
        latest_sender_rfc_id=parsed.rfc_message_id,
        updated_at="",
    )
    return save_approval(connection, approval)
