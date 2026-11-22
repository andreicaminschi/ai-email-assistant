import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from importlib.resources import files
from types import MappingProxyType

QUOTE_LIMIT = 1000
PLACEHOLDER_PATTERN = re.compile(r"\{(\w+)\}")
URGENT_PART_PATTERN = re.compile(r"\[urgent: ([^\]]*)\]")
REPLY_PREFIX_PATTERN = re.compile(r"^(?:\s*re:\s*)+", re.IGNORECASE)
REPLY_SUBJECT = "Re: {original_subject}"


class TemplateName(StrEnum):
    SALES_DECLINE = "sales_decline"
    APPROVAL_TASK = "approval_task"
    APPROVAL_MEETING = "approval_meeting"
    ASK_FOR_DATE = "ask_for_date"
    TASK_APPROVED = "task_approved"
    TASK_REJECTED = "task_rejected"
    MEETING_DECLINED = "meeting_declined"
    ACKNOWLEDGEMENT = "acknowledgement"


@dataclass(frozen=True)
class ApprovalSubject:
    normal: str
    urgent: str


APPROVAL_SUBJECTS: Mapping[TemplateName, ApprovalSubject] = MappingProxyType(
    {
        TemplateName.APPROVAL_TASK: ApprovalSubject(
            "Approval needed: {original_subject}", "Urgent approval needed: {original_subject}"
        ),
        TemplateName.APPROVAL_MEETING: ApprovalSubject(
            "Meeting request: {original_subject}", "Urgent meeting request: {original_subject}"
        ),
    }
)


@dataclass(frozen=True)
class RenderedEmail:
    name: TemplateName
    subject: str
    body: str
    replies_to_sender: bool


class TemplateValueMissing(Exception):
    pass


def read_template_text(name: TemplateName) -> str:
    return files("email_agent").joinpath("templates", f"{name}.txt").read_text(encoding="utf-8")


def read_subject_template(name: TemplateName, urgent: bool) -> str:
    approval_subject = APPROVAL_SUBJECTS.get(name)
    if approval_subject is None:
        return REPLY_SUBJECT
    return approval_subject.urgent if urgent else approval_subject.normal


def resolve_urgent_parts(text: str, urgent: bool) -> str:
    return URGENT_PART_PATTERN.sub(r"\1" if urgent else "", text)


def fill_placeholders(name: TemplateName, text: str, values: Mapping[str, str]) -> str:
    placeholders = PLACEHOLDER_PATTERN.findall(text)
    missing = [placeholder for placeholder in placeholders if placeholder not in values]
    if missing:
        raise TemplateValueMissing(f"missing value for {{{missing[0]}}} in {name}")
    return PLACEHOLDER_PATTERN.sub(lambda match: values[match.group(1)], text)


def render_template(name: TemplateName, values: Mapping[str, str], urgent: bool) -> RenderedEmail:
    subject = fill_placeholders(name, read_subject_template(name, urgent), values)
    body = fill_placeholders(name, resolve_urgent_parts(read_template_text(name), urgent), values)
    return RenderedEmail(name, subject, body, name not in APPROVAL_SUBJECTS)


def strip_reply_prefix(subject: str) -> str:
    return REPLY_PREFIX_PATTERN.sub("", subject)


def read_sender_name(from_name: str, from_address: str) -> str:
    return from_name or from_address


def format_quoted_text(text: str) -> str:
    return "\n".join(f"> {line}" for line in text[:QUOTE_LIMIT].splitlines())


def format_slot(day: date, start: time, duration_minutes: int) -> str:
    start_at = datetime.combine(day, start)
    end_at = start_at + timedelta(minutes=duration_minutes)
    return f"{start_at:%a} {start_at.day} {start_at:%b %H:%M}–{end_at:%H:%M}"
