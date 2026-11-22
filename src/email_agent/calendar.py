from pathlib import Path
from typing import TYPE_CHECKING

from googleapiclient.discovery import build  # pyright: ignore[reportUnknownVariableType]

from email_agent.google_auth import load_credentials

if TYPE_CHECKING:
    from googleapiclient._apis.calendar.v3 import CalendarResource  # pyright: ignore[reportMissingModuleSource]


def build_calendar(secrets_dir: Path) -> CalendarResource:
    credentials = load_credentials(secrets_dir / "calendar_token")
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def get_primary_calendar_id(calendar: CalendarResource) -> str:
    entry = calendar.calendarList().get(calendarId="primary").execute()
    return entry.get("id", "")
