from dataclasses import dataclass

from email_agent.approval.reply_match import Answer
from email_agent.audit import Action
from email_agent.db import ApprovalRow
from email_agent.sender import OutgoingEmail
from email_agent.templates import TemplateName, render_template


@dataclass(frozen=True)
class TaskAnswer:
    outgoing: OutgoingEmail
    action: Action


def build_task_answer(approval: ApprovalRow, answer: Answer) -> TaskAnswer:
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
    rendered = render_template(name, values, urgent=False)
    outgoing = OutgoingEmail(
        to=approval.sender_email,
        rendered=rendered,
        thread_id=approval.original_thread_id,
        in_reply_to=approval.latest_sender_rfc_id,
    )
    action = Action.SEND_TASK_APPROVED if approved else Action.SEND_TASK_REJECTED
    return TaskAnswer(outgoing, action)
