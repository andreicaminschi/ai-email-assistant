import base64
import re
from dataclasses import dataclass
from email.errors import HeaderParseError
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import parseaddr
from typing import TYPE_CHECKING

from email_agent.gmail import get_full_message
from email_agent.html_text import HtmlText, Link, convert_html, read_link_domain

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource  # pyright: ignore[reportMissingModuleSource]
    from googleapiclient._apis.gmail.v1.schemas import Message, MessagePart  # pyright: ignore[reportMissingModuleSource]

BODY_LIMIT = 1000
PLAIN_URL_PATTERN = re.compile(r"https?://[^\s<>\"'()\[\]]+", re.IGNORECASE)

type Headers = tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Attachment:
    name: str
    size: int


@dataclass(frozen=True)
class EmailBodies:
    label_body: str
    follow_up_body: str
    links: tuple[Link, ...]


@dataclass(frozen=True)
class ParsedEmail:
    message_id: str
    thread_id: str
    from_name: str
    from_address: str
    to: str
    reply_to: str
    subject: str
    date: str
    rfc_message_id: str
    headers: Headers
    label_body: str
    follow_up_body: str
    links: tuple[Link, ...]
    attachments: tuple[Attachment, ...]


def read_header_values(headers: Headers, name: str) -> tuple[str, ...]:
    wanted = name.casefold()
    return tuple(value for header_name, value in headers if header_name.casefold() == wanted)


def read_header(headers: Headers, name: str) -> str:
    values = read_header_values(headers, name)
    return values[0] if values else ""


def decode_header_text(value: str) -> str:
    try:
        return str(make_header(decode_header(value)))
    except (HeaderParseError, LookupError, UnicodeDecodeError):
        return value


def read_part_headers(part: MessagePart) -> Headers:
    return tuple((header.get("name", ""), header.get("value", "")) for header in part.get("headers", []))


def list_parts(part: MessagePart) -> list[MessagePart]:
    """
    @example
    list_parts({"mimeType": "multipart/mixed", "parts": [
        {"mimeType": "multipart/alternative", "parts": [{"mimeType": "text/plain"}]},
        {"mimeType": "application/pdf", "filename": "invoice.pdf"},
    ]})
    # → [multipart/mixed, multipart/alternative, text/plain, application/pdf]
    """
    return [part, *(nested for child in part.get("parts", []) for nested in list_parts(child))]


def read_part_charset(part: MessagePart) -> str:
    content_type = EmailMessage()
    content_type["Content-Type"] = read_header(read_part_headers(part), "Content-Type") or "text/plain"
    return content_type.get_content_charset() or "utf-8"


def decode_part_text(part: MessagePart) -> str:
    data = part.get("body", {}).get("data", "")
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    try:
        text = raw.decode(read_part_charset(part), errors="replace")
    except LookupError:
        text = raw.decode("utf-8", errors="replace")
    return text.replace("\r\n", "\n")


def find_text_part(parts: list[MessagePart], mime_type: str) -> str | None:
    texts = [
        decode_part_text(part)
        for part in parts
        if part.get("mimeType", "").lower() == mime_type and not part.get("filename")
    ]
    return texts[0] if texts else None


def find_plain_links(text: str) -> tuple[Link, ...]:
    """
    @example
    find_plain_links("Pick a time at https://cal.com/x or https://Cal.com/y")
    # → (Link(text="", domain="cal.com"),)
    """
    domains = (read_link_domain(url) for url in PLAIN_URL_PATTERN.findall(text))
    return tuple(dict.fromkeys(Link(text="", domain=domain) for domain in domains if domain))


def build_bodies(plain: str | None, html: HtmlText | None) -> EmailBodies:
    links = html.links if html is not None else find_plain_links(plain or "")
    if plain is not None:
        return EmailBodies(plain[:BODY_LIMIT], plain[:BODY_LIMIT], links)
    if html is not None:
        return EmailBodies(html.text_with_domains[:BODY_LIMIT], html.text[:BODY_LIMIT], links)
    return EmailBodies("", "", links)


def list_attachments(parts: list[MessagePart]) -> tuple[Attachment, ...]:
    return tuple(
        Attachment(name=part.get("filename", ""), size=part.get("body", {}).get("size", 0))
        for part in parts
        if part.get("filename")
    )


def parse_message(message: Message) -> ParsedEmail:
    payload = message.get("payload", {})
    headers = read_part_headers(payload)
    parts = list_parts(payload)
    html = find_text_part(parts, "text/html")
    bodies = build_bodies(
        find_text_part(parts, "text/plain"),
        convert_html(html) if html is not None else None,
    )
    from_name, from_address = parseaddr(read_header(headers, "From"))
    _reply_to_name, reply_to = parseaddr(read_header(headers, "Reply-To"))
    return ParsedEmail(
        message_id=message.get("id", ""),
        thread_id=message.get("threadId", ""),
        from_name=decode_header_text(from_name),
        from_address=from_address,
        to=decode_header_text(read_header(headers, "To")),
        reply_to=reply_to,
        subject=decode_header_text(read_header(headers, "Subject")),
        date=read_header(headers, "Date"),
        rfc_message_id=read_header(headers, "Message-ID"),
        headers=headers,
        label_body=bodies.label_body,
        follow_up_body=bodies.follow_up_body,
        links=bodies.links,
        attachments=list_attachments(parts),
    )


def fetch_parsed_email(gmail: GmailResource, message_id: str) -> ParsedEmail | None:
    message = get_full_message(gmail, message_id)
    return parse_message(message) if message is not None else None
