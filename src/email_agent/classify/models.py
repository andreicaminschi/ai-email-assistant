from datetime import date, time
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Label(StrEnum):
    MEETING_REQUEST = "MEETING_REQUEST"
    TASK = "TASK"
    INFO_ONLY = "INFO_ONLY"
    SALES_OUTREACH = "SALES_OUTREACH"
    MARKETING = "MARKETING"
    SPAM = "SPAM"
    UNCLASSIFIED = "UNCLASSIFIED"


class LabelResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: Label
    reason: str = Field(description="One sentence on why this label fits.")


class Triage(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: Label
    reason: str
    meeting_date: date | None = None
    date_quote: str | None = None
    meeting_time: time | None = None
    time_quote: str | None = None
    is_invoice: bool | None = None
    invoice_evidence: str | None = None
    urgent: bool | None = None
    evidence: str | None = None
