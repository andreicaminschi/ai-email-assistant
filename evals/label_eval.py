import base64
import os
import sys
from collections.abc import Mapping
from email import message_from_string, policy
from email.message import EmailMessage, MIMEPart
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import EqualsExpected

from email_agent.checks import SenderFlags, read_sender_flags
from email_agent.classify.models import Label
from email_agent.classify.tree import build_tree_agents, run_label_call
from email_agent.config import Settings, SettingsError, load_settings, strip_and_drop_empty
from email_agent.llm import LlmConfigError, build_model
from email_agent.message import ParsedEmail, parse_message

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1.schemas import (  # pyright: ignore[reportMissingModuleSource]
        Message,
        MessagePart,
        MessagePartHeader,
    )

REPO_DIR = Path(__file__).resolve().parent.parent
SAMPLES_DIR = REPO_DIR / "samples"
AGENT_EMAIL_PLACEHOLDER = "{{AGENT_EMAIL}}"
SAMPLE_INTERNAL_DOMAINS = ("acme.com",)

EXPECTED_LABELS: Mapping[str, Label] = MappingProxyType(
    {
        "ext-cold-pitch": Label.SALES_OUTREACH,
        "ext-fyi": Label.INFO_ONLY,
        "ext-invoice": Label.INFO_ONLY,
        "ext-marketing-urgent": Label.MARKETING,
        "ext-meeting-date-only": Label.MEETING_REQUEST,
        "ext-meeting-date-time": Label.MEETING_REQUEST,
        "ext-meeting-no-date": Label.MEETING_REQUEST,
        "ext-newsletter": Label.MARKETING,
        "ext-phishing": Label.SPAM,
        "ext-task-quote": Label.TASK,
        "ext-task-urgent": Label.TASK,
        "ext-unclassified": Label.UNCLASSIFIED,
        "int-dmarc-fail": Label.SPAM,
        "int-meeting": Label.MEETING_REQUEST,
        "int-report": Label.UNCLASSIFIED,
        "int-task-pto-urgent": Label.TASK,
    }
)


def build_gmail_part(part: MIMEPart) -> MessagePart:
    """The shape Gmail's API returns for a part."""
    headers: list[MessagePartHeader] = [
        {"name": name, "value": str(value)} for name, value in part.items()
    ]
    if part.is_multipart():
        children = [build_gmail_part(child) for child in part.iter_parts()]
        return {"mimeType": part.get_content_type(), "headers": headers, "parts": children}
    payload = part.get_payload(decode=True)
    data = payload if isinstance(payload, bytes) else b""
    return {
        "mimeType": part.get_content_type(),
        "headers": headers,
        "filename": part.get_filename() or "",
        "body": {"data": base64.urlsafe_b64encode(data).decode("ascii"), "size": len(data)},
    }


def read_sample(name: str, agent_email: str) -> ParsedEmail:
    text = (SAMPLES_DIR / f"{name}.eml").read_text(encoding="utf-8")
    email = message_from_string(
        text.replace(AGENT_EMAIL_PLACEHOLDER, agent_email), _class=EmailMessage, policy=policy.default
    )
    message: Message = {"id": name, "threadId": name, "payload": build_gmail_part(email)}
    return parse_message(message)


def build_dataset() -> Dataset[str, Label, None]:
    cases = [Case(name=name, inputs=name, expected_output=label) for name, label in EXPECTED_LABELS.items()]
    return Dataset(name="label", cases=cases, evaluators=[EqualsExpected()])


def main() -> int:
    try:
        settings = load_settings(strip_and_drop_empty(os.environ))
        model = build_model(settings)
    except (SettingsError, LlmConfigError) as error:
        print(error)
        return 1
    sample_settings: Settings = settings.model_copy(update={"internal_domains": SAMPLE_INTERNAL_DOMAINS})
    agents = build_tree_agents(model)
    samples = {name: read_sample(name, settings.agent_email) for name in EXPECTED_LABELS}
    flags: Mapping[str, SenderFlags] = {
        name: read_sender_flags(parsed, sample_settings) for name, parsed in samples.items()
    }

    def label_sample(name: str) -> Label:
        return run_label_call(agents, samples[name], flags[name]).label

    report = build_dataset().evaluate_sync(label_sample, max_concurrency=4)
    report.print(include_expected_output=True, include_output=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
