from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from email_agent.audit import Action
from email_agent.classify.models import Label, Triage
from email_agent.config import RunMode
from email_agent.db import State
from email_agent.message import ParsedEmail

DEV_SPAM_LABEL = "This is spam"


@dataclass(frozen=True)
class HandlerInput:
    parsed: ParsedEmail
    triage: Triage
    label_ids: Mapping[str, str]
    run_mode: RunMode


@dataclass(frozen=True)
class HandlerResult:
    add_label_ids: tuple[str, ...]
    remove_label_ids: tuple[str, ...]
    action: Action
    state: State


type Handler = Callable[[HandlerInput], HandlerResult]


def tag_with_label(handler_input: HandlerInput) -> HandlerResult:
    label_id = handler_input.label_ids[handler_input.triage.label]
    return HandlerResult((label_id,), (), Action.LABEL_ONLY, State.DONE)


def tag_as_spam(handler_input: HandlerInput) -> HandlerResult:
    name = DEV_SPAM_LABEL if handler_input.run_mode is RunMode.DEV else Label.SPAM
    return HandlerResult((handler_input.label_ids[name],), (), Action.LABEL_ONLY, State.DONE)


def do_nothing(_handler_input: HandlerInput) -> HandlerResult:
    return HandlerResult((), (), Action.NONE_UNCLASSIFIED, State.DONE)


EXTERNAL_HANDLERS: Mapping[Label, Handler] = MappingProxyType(
    {
        Label.MARKETING: tag_with_label,
        Label.SALES_OUTREACH: tag_with_label,
        Label.INFO_ONLY: tag_with_label,
        Label.SPAM: tag_as_spam,
        Label.MEETING_REQUEST: tag_with_label,
        Label.TASK: tag_with_label,
        Label.UNCLASSIFIED: do_nothing,
    }
)

INTERNAL_HANDLERS: Mapping[Label, Handler] = MappingProxyType(
    {
        Label.MEETING_REQUEST: EXTERNAL_HANDLERS[Label.MEETING_REQUEST],
        Label.TASK: EXTERNAL_HANDLERS[Label.TASK],
        Label.UNCLASSIFIED: do_nothing,
    }
)


def find_handler(internal: bool, label: Label) -> Handler:
    if internal:
        # Other labels: unclassified
        return INTERNAL_HANDLERS.get(label, do_nothing)
    return EXTERNAL_HANDLERS[label]
