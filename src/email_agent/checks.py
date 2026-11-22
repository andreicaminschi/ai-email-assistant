import re
from dataclasses import dataclass

from email_agent.config import Settings
from email_agent.message import Headers, ParsedEmail, read_header, read_header_values

GMAIL_AUTHSERV_ID = "mx.google.com"
DMARC_PATTERN = re.compile(r"dmarc\s*=\s*([a-z]+)", re.IGNORECASE)
BULK_HEADERS = ("List-Unsubscribe", "List-Id")


@dataclass(frozen=True)
class SenderFlags:
    internal: bool
    bulk: bool
    dmarc: str | None


def read_address_domain(address: str) -> str:
    return address.rpartition("@")[2].casefold()


def is_own_mail(parsed: ParsedEmail, agent_email: str) -> bool:
    return parsed.from_address.casefold() == agent_email.casefold()


def read_first_token(text: str) -> str:
    return (text.split(";")[0].split() or [""])[0].casefold()


def is_auto_reply(headers: Headers) -> bool:
    return read_first_token(read_header(headers, "Auto-Submitted")) not in ("", "no")


def read_dmarc_result(value: str) -> str | None:
    """
    @example
    read_dmarc_result("mx.google.com; arc=pass (dmarc=pass); dmarc=fail") == "fail"
    """
    results = [part.strip() for part in value.split(";")[1:]]
    dmarc_results = [part for part in results if part.casefold().startswith("dmarc")]
    match = DMARC_PATTERN.match(dmarc_results[0]) if dmarc_results else None
    return match.group(1).casefold() if match else None


def read_dmarc(headers: Headers) -> str | None:
    gmail_values = [
        value
        for value in read_header_values(headers, "Authentication-Results")
        if read_first_token(value) == GMAIL_AUTHSERV_ID
    ]
    return read_dmarc_result(gmail_values[0]) if gmail_values else None


def is_internal(address: str, dmarc: str | None, settings: Settings) -> bool:
    listed = (
        read_address_domain(address) in settings.internal_domains
        or address.casefold() in settings.internal_addresses
    )
    return listed and dmarc == "pass"


def is_bulk_domain(domain: str, bulk_domains: tuple[str, ...]) -> bool:
    return any(domain == bulk or domain.endswith(f".{bulk}") for bulk in bulk_domains)


def has_bulk_headers(headers: Headers) -> bool:
    listed = any(read_header(headers, name) for name in BULK_HEADERS)
    return listed or read_header(headers, "Precedence").strip().casefold() == "bulk"


def read_sender_flags(parsed: ParsedEmail, settings: Settings) -> SenderFlags:
    dmarc = read_dmarc(parsed.headers)
    bulk = has_bulk_headers(parsed.headers) or is_bulk_domain(
        read_address_domain(parsed.from_address), settings.bulk_domains
    )
    return SenderFlags(
        internal=is_internal(parsed.from_address, dmarc, settings), bulk=bulk, dmarc=dmarc
    )
