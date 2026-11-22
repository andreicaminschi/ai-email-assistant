from datetime import date, time
from enum import StrEnum
from typing import Literal

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


class InternalLabelResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: Literal[Label.MEETING_REQUEST, Label.TASK, Label.UNCLASSIFIED]
    reason: str = Field(description="One sentence on why this label fits.")


class TimesResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    meeting_date: date | None = Field(default=None, description="YYYY-MM-DD, or empty.")
    date_quote: str | None = Field(
        default=None, description="The exact words in the email that carry the date."
    )
    meeting_time: time | None = Field(default=None, description="HH:MM in 24-hour form, or empty.")
    time_quote: str | None = Field(
        default=None, description="The exact words in the email that carry the time."
    )


class InvoiceResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_invoice: bool
    evidence: str | None = Field(
        default=None, description="The exact words in the email that show it, or empty."
    )


class UrgentResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    urgent: bool
    evidence: str | None = Field(
        default=None, description="The exact words in the email that show it, or empty."
    )


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
