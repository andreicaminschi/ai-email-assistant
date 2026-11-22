from dataclasses import dataclass
from datetime import datetime

from email_agent.approval.reply_match import Answer
from email_agent.audit import Action
from email_agent.calendar import MeetingEvent
from email_agent.db import ApprovalKind, ApprovalRow
from email_agent.sender import OutgoingEmail
from email_agent.templates import TemplateName, format_slot, render_template


@dataclass(frozen=True)
class ApprovalAnswer:
    """One of outgoing or event is set."""

    action: Action
    outgoing: OutgoingEmail | None = None
    event: MeetingEvent | None = None


@dataclass(frozen=True)
class MeetingTimes:
    start: datetime
    end: datetime


def build_sender_answer(
    approval: ApprovalRow, name: TemplateName, values: dict[str, str]
) -> OutgoingEmail:
    """In the original thread, to Reply-To or From."""
    rendered = render_template(name, values, urgent=False)
    return OutgoingEmail(
        to=approval.sender_email,
        rendered=rendered,
        thread_id=approval.original_thread_id,
        in_reply_to=approval.latest_sender_rfc_id,
    )


def build_task_answer(approval: ApprovalRow, answer: Answer) -> ApprovalAnswer:
    """
    @example
    build_task_answer(pto_approval, Answer.NO).outgoing.rendered.name
    # → TemplateName.TASK_REJECTED, in the original thread
    """
    approved = answer is Answer.YES
    name = TemplateName.TASK_APPROVED if approved else TemplateName.TASK_REJECTED
    values = {
        "sender_name": approval.sender_name,
        "original_subject": approval.original_subject,
    }
    action = Action.SEND_TASK_APPROVED if approved else Action.SEND_TASK_REJECTED
    return ApprovalAnswer(action, outgoing=build_sender_answer(approval, name, values))


def read_meeting_times(approval: ApprovalRow) -> MeetingTimes | None:
    if approval.meeting_start is None or approval.meeting_end is None:
        return None
    start = datetime.fromisoformat(approval.meeting_start)
    end = datetime.fromisoformat(approval.meeting_end)
    return MeetingTimes(start, end)


def build_meeting_answer(
    approval: ApprovalRow, answer: Answer, times: MeetingTimes
) -> ApprovalAnswer:
    """
    @example
    build_meeting_answer(tom_approval, Answer.YES, times).event.event_id
    # → the forward's threadId
    build_meeting_answer(tom_approval, Answer.NO, times).outgoing.rendered.body
    # → "...Unfortunately we can't make Thu 26 Nov 14:00–14:30..."
    """
    if answer is Answer.YES:
        event = MeetingEvent(
            event_id=approval.forward_thread_id,
            title=approval.original_subject,
            start=times.start,
            end=times.end,
            attendee_email=approval.sender_email,
        )
        return ApprovalAnswer(Action.CREATE_EVENT, event=event)
    duration_minutes = int((times.end - times.start).total_seconds() // 60)
    slot = format_slot(times.start.date(), times.start.time(), duration_minutes)
    values = {
        "sender_name": approval.sender_name,
        "original_subject": approval.original_subject,
        "slot": slot,
    }
    outgoing = build_sender_answer(approval, TemplateName.MEETING_DECLINED, values)
    return ApprovalAnswer(Action.SEND_MEETING_DECLINE, outgoing=outgoing)


def build_approval_answer(approval: ApprovalRow, answer: Answer) -> ApprovalAnswer | None:
    """None: a meeting approval without its times."""
    if approval.kind is ApprovalKind.TASK:
        return build_task_answer(approval, answer)
    times = read_meeting_times(approval)
    if times is None:
        return None
    return build_meeting_answer(approval, answer, times)
