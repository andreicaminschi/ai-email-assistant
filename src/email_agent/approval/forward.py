import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

from email_agent.config import Settings
from email_agent.db import ApprovalKind, ApprovalRow, State, save_approval
from email_agent.message import ParsedEmail
from email_agent.sender import OutgoingEmail, send_once
from email_agent.templates import (
    TemplateName,
    format_quoted_text,
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


def build_task_forward(parsed: ParsedEmail, urgent: bool, manager_email: str) -> ApprovalForward:
    """
    @example
    build_task_forward(pto_email, True, "boss@x.com").outgoing.rendered.subject
    # → "Urgent approval needed: PTO"
    """
    sender_name = read_sender_name(parsed.from_name, parsed.from_address)
    original_subject = strip_reply_prefix(parsed.subject)
    values = {
        "sender_name": sender_name,
        "sender_email": parsed.from_address,
        "quoted_text": format_quoted_text(parsed.follow_up_body),
        "original_subject": original_subject,
    }
    rendered = render_template(TemplateName.APPROVAL_TASK, values, urgent)
    # New thread: no threadId
    outgoing = OutgoingEmail(to=manager_email, rendered=rendered, thread_id=None, in_reply_to="")
    return ApprovalForward(
        ApprovalKind.TASK, outgoing, parsed.from_address, sender_name, original_subject
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
        meeting_start=None,
        meeting_end=None,
        latest_sender_rfc_id=parsed.rfc_message_id,
        updated_at="",
    )
    return save_approval(connection, approval)
