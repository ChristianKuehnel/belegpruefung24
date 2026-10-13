"""Typed models for Portal24 resources.

Every model keeps the untouched server payload in ``raw`` so that no
information is lost even before the full response schema is verified.
Fields marked as verified in docs/REVERSE_ENGINEERING.md are stable;
others are best-effort and may change as live verification proceeds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Property:
    """A managed object (property / building / WEG) visible to the user."""

    id: str
    name: str
    kind: str | None = None
    address: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class RentUnit:
    """A rent unit / administrative unit (Wohnung, WHG, ...) of the user."""

    id: str
    name: str
    kind: str | None = None
    since: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class DmsCategory:
    """A DMS document category (folder), with server-side counts.

    ``path`` is the server-derived category path (e.g. ``Parent/Child``),
    filled in by the parser from the category tree.
    """

    id: int
    name: str
    count: int = 0
    parent_id: int | None = None
    path: str = ""
    children: list[DmsCategory] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class Document:
    """A downloadable document with its logical location.

    Verified fields (live, 2026-10-13): the document list renders id,
    name, status (neu/gelesen), size, release date ("Freigabe"),
    download date ("Heruntergeladen"), and leaf category name.
    """

    id: str
    name: str
    property_id: str | None = None
    folder: str | None = None
    category: str | None = None
    size: int | None = None
    size_label: str | None = None
    content_type: str | None = None
    modified: str | None = None
    released: str | None = None
    downloaded: str | None = None
    status: str | None = None
    url: str | None = None
    download_url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class PaginationInfo:
    """Parsed from the portal's uniform paginator markup."""

    first: int
    last: int
    total: int
    page_count: int
    current_page: int = 1


@dataclass
class PaymentLine:
    """One line of the 'beschlossene Zahlungen' table."""

    label: str
    amount: float | None = None
    is_total: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class Ticket:
    """A support ticket from the communicator module."""

    id: str
    number: str | None = None
    title: str | None = None
    status: str | None = None
    system: str | None = None
    created: str | None = None
    changed: str | None = None
    url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class Transaction:
    """A single accounting booking (Online-Belegprüfung item)."""

    id: str
    date: str | None = None
    description: str | None = None
    amount: float | None = None
    currency: str | None = None
    counterparty: str | None = None
    account: str | None = None
    period: str | None = None
    document_ids: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class SyncResult:
    """Outcome of a mirror/synchronization run."""

    destination: str
    enumerated: int = 0
    downloaded: int = 0
    skipped_unchanged: int = 0
    failed: int = 0
    duplicates: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return self.failed == 0
