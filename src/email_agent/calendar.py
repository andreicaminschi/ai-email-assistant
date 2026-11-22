from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from googleapiclient.discovery import build  # pyright: ignore[reportUnknownVariableType]
from googleapiclient.errors import HttpError

from email_agent.config import RunMode
from email_agent.google_auth import load_credentials

if TYPE_CHECKING:
    from googleapiclient._apis.calendar.v3 import CalendarResource, Event  # pyright: ignore[reportMissingModuleSource]

HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409


@dataclass(frozen=True)
class MeetingEvent:
    """Local times in TIME_ZONE."""

    event_id: str
    title: str
    start: datetime
    end: datetime
    attendee_email: str


def build_calendar(secrets_dir: Path) -> CalendarResource:
    credentials = load_credentials(secrets_dir / "calendar_token", "Calendar")
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def get_primary_calendar_id(calendar: CalendarResource) -> str:
    entry = calendar.calendarList().get(calendarId="primary").execute()
    return entry.get("id", "")


def build_event_body(event: MeetingEvent, time_zone: ZoneInfo) -> Event:
    return {
        "id": event.event_id,
        "summary": event.title,
        "start": {"dateTime": event.start.isoformat(), "timeZone": time_zone.key},
        "end": {"dateTime": event.end.isoformat(), "timeZone": time_zone.key},
        "attendees": [{"email": event.attendee_email}],
    }


def has_event(calendar: CalendarResource, event_id: str) -> bool:
    """A cancelled event still counts."""
    try:
        calendar.events().get(calendarId="primary", eventId=event_id).execute()
    except HttpError as error:
        if error.status_code == HTTP_NOT_FOUND:
            return False
        raise
    return True


def book_meeting(
    calendar: CalendarResource, run_mode: RunMode, time_zone: ZoneInfo, event: MeetingEvent
) -> bool:
    """
    Inserts with a fixed ID. True: created now. False: a rerun, or dev.

    @example
    book_meeting(calendar, RunMode.PROD, tz, tom_event)  # → True, Tom gets the invite
    book_meeting(calendar, RunMode.PROD, tz, tom_event)  # → False, 409 already created
    """
    if run_mode is RunMode.DEV:
        print(f"DEV would book {event.start:%Y-%m-%d %H:%M}-{event.end:%H:%M} {event.title}")
        return False
    body = build_event_body(event, time_zone)
    try:
        calendar.events().insert(calendarId="primary", body=body, sendUpdates="all").execute()
    except HttpError as error:
        if error.status_code == HTTP_CONFLICT:
            return False
        raise
    return True
