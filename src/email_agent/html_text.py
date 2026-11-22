from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urlsplit

BLOCK_TAGS = frozenset(
    {
        "address", "article", "blockquote", "br", "dd", "div", "dl", "dt", "footer",
        "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li", "ol", "p", "pre",
        "section", "table", "td", "th", "tr", "ul",
    }
)
SKIPPED_TAGS = frozenset({"head", "script", "style", "title"})
LINK_SCHEMES = frozenset({"http", "https"})


@dataclass(frozen=True)
class Link:
    text: str
    domain: str


@dataclass(frozen=True)
class HtmlText:
    text_with_domains: str
    text: str
    links: tuple[Link, ...]


def read_link_domain(href: str) -> str | None:
    try:
        parts = urlsplit(href.strip())
    except ValueError:
        return None
    if parts.scheme.lower() not in LINK_SCHEMES or not parts.hostname:
        return None
    return parts.hostname


def collapse_whitespace(text: str) -> str:
    lines = (" ".join(line.split()) for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


class HtmlTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_chunks: list[str] = []
        self.domain_text_chunks: list[str] = []
        self.links: list[Link] = []
        self.skipped_depth = 0
        self.in_link = False
        self.link_domain: str | None = None
        self.link_text_chunks: list[str] = []

    def write_text(self, text: str) -> None:
        self.text_chunks.append(text)
        self.domain_text_chunks.append(text)

    def open_link(self, href: str) -> None:
        self.in_link = True
        self.link_domain = read_link_domain(href)
        self.link_text_chunks = []

    def close_link(self) -> None:
        if self.link_domain is not None:
            link_text = " ".join("".join(self.link_text_chunks).split())
            self.links.append(Link(text=link_text, domain=self.link_domain))
            if link_text:
                self.domain_text_chunks.append(f" ({self.link_domain})")
        self.in_link = False
        self.link_domain = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in SKIPPED_TAGS:
            self.skipped_depth += 1
            return
        if tag in BLOCK_TAGS:
            self.write_text("\n")
        if tag == "a":
            if self.in_link:
                self.close_link()
            self.open_link(dict(attrs).get("href") or "")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIPPED_TAGS:
            self.skipped_depth = max(0, self.skipped_depth - 1)
            return
        if tag == "a" and self.in_link:
            self.close_link()
        if tag in BLOCK_TAGS:
            self.write_text("\n")

    def handle_data(self, data: str) -> None:
        if self.skipped_depth:
            return
        self.write_text(data)
        if self.in_link:
            self.link_text_chunks.append(data)

    def build_html_text(self) -> HtmlText:
        if self.in_link:
            self.close_link()
        return HtmlText(
            text_with_domains=collapse_whitespace("".join(self.domain_text_chunks)),
            text=collapse_whitespace("".join(self.text_chunks)),
            links=tuple(dict.fromkeys(self.links)),
        )


def convert_html(html: str) -> HtmlText:
    parser = HtmlTextParser()
    parser.feed(html)
    parser.close()
    return parser.build_html_text()
