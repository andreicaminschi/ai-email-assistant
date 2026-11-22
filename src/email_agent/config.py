from collections.abc import Mapping
from datetime import time
from enum import StrEnum
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PositiveInt, ValidationError


class SettingsError(Exception):
    pass


class RunMode(StrEnum):
    DEV = "dev"
    PROD = "prod"


def split_list(value: object) -> object:
    if not isinstance(value, str):
        return value
    return tuple(part.strip().lower() for part in value.split(",") if part.strip())


def parse_time_zone(value: object) -> object:
    if not isinstance(value, str):
        return value
    try:
        return ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"unknown time zone {value}") from None


type LowerCaseList = Annotated[tuple[str, ...], BeforeValidator(split_list)]
type TimeZone = Annotated[ZoneInfo, BeforeValidator(parse_time_zone)]


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    agent_email: str = Field(alias="AGENT_EMAIL")
    manager_email: str = Field(alias="MANAGER_EMAIL")
    run_mode: RunMode = Field(alias="RUN_MODE")
    llm_model: str = Field(alias="LLM_MODEL")
    llm_base_url: str | None = Field(default=None, alias="LLM_BASE_URL")
    internal_domains: LowerCaseList = Field(default=(), alias="INTERNAL_DOMAINS")
    internal_addresses: LowerCaseList = Field(default=(), alias="INTERNAL_ADDRESSES")
    bulk_domains: LowerCaseList = Field(default=(), alias="BULK_DOMAINS")
    poll_seconds: PositiveInt = Field(default=5, alias="POLL_SECONDS")
    time_zone: TimeZone = Field(alias="TIME_ZONE")
    meeting_default_time: time = Field(default=time(10, 0), alias="MEETING_DEFAULT_TIME")
    meeting_duration_minutes: PositiveInt = Field(default=30, alias="MEETING_DURATION_MINUTES")
    send_sales_decline: bool = Field(default=True, alias="SEND_SALES_DECLINE")
    secrets_dir: Path = Field(default=Path("/run/secrets"), alias="SECRETS_DIR")
    data_dir: Path = Field(default=Path("/data"), alias="DATA_DIR")


def strip_and_drop_empty(environ: Mapping[str, str]) -> dict[str, str]:
    return {name: value.strip() for name, value in environ.items() if value.strip()}


def format_settings_error(error: ValidationError) -> str:
    first = error.errors()[0]
    name = str(first["loc"][0])
    if first["type"] == "missing":
        return f"Missing required setting {name}"
    reason = first["msg"].removeprefix("Value error, ")
    return f"Invalid setting {name}: {reason}"


def load_settings(variables: Mapping[str, str]) -> Settings:
    try:
        return Settings.model_validate(variables)
    except ValidationError as error:
        raise SettingsError(format_settings_error(error)) from None


def read_secret(settings: Settings, name: str) -> str:
    return (settings.secrets_dir / name).read_text(encoding="utf-8").rstrip()
