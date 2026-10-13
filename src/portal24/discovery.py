"""Resource discovery.

Portal24 is a server-rendered application: business endpoints are
injected per page (links, ``data-url`` attributes, paginator hrefs).
This module implements a conservative, GET-only enumeration of
same-origin links from authenticated pages.

Raw link discovery is exposed as a safety net; the typed resource
parsers (see :mod:`portal24.dms`) are the primary interface and have
been verified against a live tenant portal (2026-10-13).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from .http import Portal24HTTP

_HREF_RE = re.compile(r"""<a\b[^>]*\bhref=["']([^"']+)["']""", re.IGNORECASE)
_DATA_URL_RE = re.compile(r"""data-(?:ajax-)?url=["']([^"']+)["']""", re.IGNORECASE)

#: Substrings that indicate a link performs a state change and must never
#: be followed by a read-only client.
#:
#: Verified against the live tenant portal (2026-10-13): several GET
#: endpoints mutate server-side session/business state, in particular
#: the object/rent-unit/data-source switchers, bulk category assignment
#: (``/dms/category/link/{id}/-1``), selection endpoints, and
#: mark-as-read actions.
_UNSAFE_MARKERS = (
    "select", "deselect", "upload", "delete", "remove", "approve", "reject",
    "comment", "send", "submit", "create", "edit", "update", "save", "drop",
    "logout", "register", "reset-password", "activate", "signature", "sign",
    "download-as", "export-create",
    # session-context switchers (GET with side effects)
    "switch-object", "switch-rent-unit", "switch-data-source",
    # bulk category assignment (GET with side effects)
    "category/link",
    # read/seen state mutations
    "mark-", "mark_", "revoke-", "jump/",
)


@dataclass(frozen=True)
class Link:
    path: str
    source: str  # "href" | "data-url"


def _is_safe(path: str) -> bool:
    lowered = path.lower().split("?", 1)[0]
    return not any(marker in lowered for marker in _UNSAFE_MARKERS)


def extract_links(page_html: str, base_url: str) -> list[Link]:
    """Extract safe, same-origin, GET-able links from an HTML page."""
    origin = urlsplit(base_url)
    found: dict[str, str] = {}
    decoded = html.unescape(page_html)

    for pattern, source in ((_HREF_RE, "href"), (_DATA_URL_RE, "data-url")):
        for match in pattern.finditer(decoded):
            target = match.group(1).strip()
            if not target or target.startswith(("javascript:", "mailto:", "#")):
                continue
            if target.startswith("//"):
                target = origin.scheme + ":" + target
            parts = urlsplit(target)
            if parts.scheme and (parts.scheme, parts.netloc) != (origin.scheme, origin.netloc):
                continue
            path = parts.path or "/"
            if parts.query:
                path = f"{path}?{parts.query}"
            if _is_safe(path) and path not in found:
                found[path] = source

    return [Link(path=p, source=s) for p, s in sorted(found.items())]


def fetch_page(http: Portal24HTTP, path: str) -> str:
    response = http.get(path)
    if response.status_code == 404:
        return ""
    if response.status_code != 200:
        from .errors import ParseError

        raise ParseError(f"Page {path} returned HTTP {response.status_code}.")
    return response.text


def discover(http: Portal24HTTP, start_paths: tuple[str, ...] = ("/",)) -> list[Link]:
    """Enumerate safe links reachable from the given starting pages."""
    links: dict[str, Link] = {}
    for path in start_paths:
        page = fetch_page(http, path)
        if not page:
            continue
        for link in extract_links(page, http.base_url):
            links.setdefault(link.path, link)
    return list(links.values())
