"""Parsers and iterators for the verified DMS (document) endpoints.

Verified live 2026-10-13 (see docs/REVERSE_ENGINEERING.md):

* ``GET /dms/document/list/{categoryId}?page=N`` — document list,
  ``categoryId = -1`` means all categories; 24 rows per page.
* ``GET /dms/document/download/{id}`` — original binary download.
* ``GET /dms/category/list`` — flat category table.
* The document list page embeds the full category tree as inline
  ``DmsCategory`` builder scripts.
* The object/rent-unit switcher columns on ``/portal/object/show``
  list all accessible objects and rent units (their links are
  state-changing and are parsed but never followed).
"""

from __future__ import annotations

import html
import re

from .http import Portal24HTTP
from .models import (
    DmsCategory,
    Document,
    PaginationInfo,
    Property,
    RentUnit,
    Ticket,
)

DOC_LIST_PATH = "/dms/document/list/{category}"
DOC_DOWNLOAD_PATH = "/dms/document/download/{id}"
CATEGORY_LIST_PATH = "/dms/category/list"
OBJECT_SHOW_PATH = "/portal/object/show"
TICKET_LIST_PATH = "/communicator/ticket/list"

_ROW_RE = re.compile(r'<tr class="[^"]*selectableRow">.*?</tr>', re.DOTALL)
_CHECKBOX_ID_RE = re.compile(
    r'class="singleCheckbox multiSelectTableCheckbox"\s+value="(\d+)"', re.DOTALL
)
_STATUS_RE = re.compile(r'<label class="label[^"]*">\s*(neu|gelesen)\s*</label>', re.DOTALL)
_NAME_CELL_RE = re.compile(r'<td[^>]*title="([^"]*)"', re.DOTALL)
_SHOW_LINK_RE = re.compile(r'href="(/dms/document/show/(\d+))"')
_DOWNLOAD_LINK_RE = re.compile(r'href="(/dms/document/download/(\d+))"')

_PAGINATOR_TITLE_RE = re.compile(
    r'<ul class="pagination[^"]*"\s+title="(\d+)\s*-\s*(\d+)\s*/\s*(\d+)\s*/\s*(\d+)"',
    re.DOTALL,
)
_ACTIVE_PAGE_RE = re.compile(r'<li class="active">\s*<a[^>]*href="[^"]*\?page=(\d+)"')

_CATEGORY_SCRIPT_RE = re.compile(
    r"new DmsCategory\(\)\s*\.setId\((\d+)\)\s*\.setName\('([^']*)'\)\s*\.setCount\((\d+)\)",
    re.DOTALL,
)
_ADDCHILD_RE = re.compile(
    r"currentCategory\.addChild\(\s*new DmsCategory\(\)\s*\.setId\((\d+)\)"
    r"\s*\.setName\('([^']*)'\)\s*\.setCount\((\d+)\)\s*\)",
    re.DOTALL,
)

_OBJECT_LINK_RE = re.compile(
    r'<div[^>]*id="objectSearchTarget">.*?</div>', re.DOTALL
)
_OBJECT_ITEM_RE = re.compile(
    r'<a href="/application/essential/switch-object/(\d+)/[^"]*"[^>]*>(.*?)</a>', re.DOTALL
)
_RUCR_LINK_RE = re.compile(
    r'<div[^>]*id="rucrSearchTarget">.*?</div>', re.DOTALL
)
_RUCR_ITEM_RE = re.compile(
    r'<a href="/application/essential/switch-rent-unit-contact-relation/(\d+)/[^"]*"'
    r"[^>]*>(.*?)</a>",
    re.DOTALL,
)
_TICKET_ROW_RE = re.compile(r'<tr data-id="(\d+)"[^>]*>.*?</tr>', re.DOTALL)
_TICKET_TITLE_RE = re.compile(
    r'<a href="(/communicator/ticket/show/\d+)"[^>]*>(.*?)</a>', re.DOTALL
)


def _text(fragment: str) -> str:
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment))).strip()


def _parse_size(label: str) -> int | None:
    match = re.match(r"([\d.,]+)\s*(B|KB|MB|GB)", label.strip(), re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1).replace(".", "").replace(",", "."))
    factor = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}[match.group(2).upper()]
    return int(value * factor)


def parse_document_rows(page_html: str) -> list[Document]:
    """Parse one page of the DMS document list table.

    Verified column order: toggler, checkbox (id), status, name, size,
    release date, download date, category, actions.
    """
    decoded = html.unescape(page_html)
    documents: list[Document] = []
    for row in _ROW_RE.finditer(decoded):
        chunk = row.group(0)
        id_match = _CHECKBOX_ID_RE.search(chunk)
        if not id_match:
            continue
        doc_id = id_match.group(1)
        name_match = _NAME_CELL_RE.search(chunk)
        show_match = _SHOW_LINK_RE.search(chunk)
        download_match = _DOWNLOAD_LINK_RE.search(chunk)

        parts = re.split(r"</td>", chunk)
        cells = [_text(p) for p in parts]
        # parts[0] holds the <tr> tag plus the first (empty) td, so the
        # data cells start at index 2: status, name, size, released,
        # downloaded, category, actions.
        status = cells[2] if len(cells) > 2 else ""
        size_label = cells[4] if len(cells) > 4 else ""
        released = cells[5] if len(cells) > 5 else ""
        downloaded = cells[6] if len(cells) > 6 else ""
        category = cells[7] if len(cells) > 7 else ""

        documents.append(
            Document(
                id=doc_id,
                name=name_match.group(1) if name_match else f"document-{doc_id}",
                status=status if status in ("neu", "gelesen") else None,
                size=_parse_size(size_label) if size_label else None,
                size_label=size_label or None,
                released=released or None,
                downloaded=downloaded or None,
                category=category or None,
                url=show_match.group(1) if show_match else None,
                download_url=download_match.group(1)
                or f"/dms/document/download/{doc_id}",
            )
        )
    return documents


def parse_pagination(page_html: str) -> PaginationInfo | None:
    decoded = html.unescape(page_html)
    match = _PAGINATOR_TITLE_RE.search(decoded)
    if not match:
        return None
    first, last, total, page_count = (int(g) for g in match.groups())
    current = 1
    active = _ACTIVE_PAGE_RE.search(decoded)
    if active:
        current = int(active.group(1))
    return PaginationInfo(
        first=first, last=last, total=total, page_count=page_count, current_page=current
    )


def parse_categories(page_html: str) -> list[DmsCategory]:
    """Parse the category tree from the embedded DmsCategory scripts."""
    decoded = html.unescape(page_html)
    by_id: dict[int, DmsCategory] = {}
    roots: list[DmsCategory] = []

    for match in _CATEGORY_SCRIPT_RE.finditer(decoded):
        cat_id, name, count = int(match.group(1)), match.group(2), int(match.group(3))
        category = DmsCategory(id=cat_id, name=name, count=count)
        by_id[cat_id] = category
        roots.append(category)

    for match in _ADDCHILD_RE.finditer(decoded):
        child_id, name, count = int(match.group(1)), match.group(2), int(match.group(3))
        child = DmsCategory(id=child_id, name=name, count=count)
        by_id[child_id] = child
        parent = _parent_of(match.start(), decoded, by_id)
        if parent is not None:
            parent.children.append(child)
            child.parent_id = parent.id
            roots = [r for r in roots if r.id != child_id]

    _fill_paths(roots, "")
    return roots


def _parent_of(position: int, decoded: str, by_id: dict[int, DmsCategory]) -> DmsCategory | None:
    """The child belongs to the most recent top-level category script.

    Only ``currentCategory = new DmsCategory()`` assignments count; the
    ``addChild`` scripts must not be mistaken for parents.
    """
    top_level_re = re.compile(r"currentCategory\s*=\s*new DmsCategory\(\)\s*\.setId\((\d+)\)")
    preceding = list(top_level_re.finditer(decoded, 0, position))
    if not preceding:
        return None
    return by_id.get(int(preceding[-1].group(1)))


def _fill_paths(categories: list[DmsCategory], parent_path: str) -> None:
    for category in categories:
        category.path = f"{parent_path}/{category.name}" if parent_path else category.name
        _fill_paths(category.children, category.path)


def parse_objects(page_html: str) -> list[Property]:
    """Parse the object switcher column (links are never followed).

    Markup: ``<a href="switch-object/{id}/{b64}">icon {name} <br/>
    <span class="text-xs">{street}, {city}</span></a>``
    """
    decoded = html.unescape(page_html)
    block_match = _OBJECT_LINK_RE.search(decoded)
    if not block_match:
        return []
    properties: list[Property] = []
    for item in _OBJECT_ITEM_RE.finditer(block_match.group(0)):
        inner = item.group(2)
        span_match = re.search(r'<span class="text-xs[^"]*">(.*?)</span>', inner, re.DOTALL)
        address = _text(span_match.group(1)) if span_match else None
        name_part = inner[: span_match.start()] if span_match else inner
        name = _text(re.sub(r"<[^>]+>", " ", name_part))
        properties.append(Property(id=item.group(1), name=name, address=address))
    return properties


def parse_rent_units(page_html: str) -> list[RentUnit]:
    """Parse the rent-unit switcher column (links are never followed).

    Markup: ``<a href="switch-rent-unit-contact-relation/{id}/{b64}">icon
    {name} <br/> <span class="text-xs">{kind}, seit {date}</span></a>``
    """
    decoded = html.unescape(page_html)
    block_match = _RUCR_LINK_RE.search(decoded)
    if not block_match:
        return []
    units: list[RentUnit] = []
    for item in _RUCR_ITEM_RE.finditer(block_match.group(0)):
        inner = item.group(2)
        span_match = re.search(r'<span class="text-xs[^"]*">(.*?)</span>', inner, re.DOTALL)
        if span_match:
            name = _text(re.sub(r"<[^>]+>", " ", inner[: span_match.start()]))
        else:
            name = _text(inner)
        kind = None
        since = None
        if span_match:
            meta = _text(span_match.group(1))
            since_match = re.search(r"seit\s+([\d.]+)", meta)
            since = since_match.group(1) if since_match else None
            kind = re.sub(r",?\s*seit\s+[\d.]+", "", meta).strip() or None
        units.append(RentUnit(id=item.group(1), name=name, kind=kind, since=since))
    return units


def parse_tickets(page_html: str) -> list[Ticket]:
    decoded = html.unescape(page_html)
    tickets: list[Ticket] = []
    for row in _TICKET_ROW_RE.finditer(decoded):
        chunk = row.group(0)
        title_match = _TICKET_TITLE_RE.search(chunk)
        cells = [_text(c) for c in re.split(r"</td>", chunk)]
        tickets.append(
            Ticket(
                id=row.group(1),
                number=next((c for c in cells if c.startswith("TSP#")), None),
                title=_text(title_match.group(2)) if title_match else None,
                url=title_match.group(1) if title_match else None,
                status=next(
                    (c for c in cells if c in ("offen", "in Bearbeitung", "geschlossen")), None
                ),
                created=next(
                    (
                        c
                        for c in cells
                        if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}, \d{2}:\d{2}:\d{2}", c)
                    ),
                    None,
                ),
            )
        )
    return tickets


# -- iterators -------------------------------------------------------------


def iter_documents(
    http: Portal24HTTP, category: int = -1, max_pages: int | None = None
):
    """Yield all documents for a category (``-1`` = all), following pages."""
    page = 1
    while True:
        path = DOC_LIST_PATH.format(category=category)
        if page > 1:
            path = f"{path}?page={page}"
        response = http.get(path)
        if response.status_code != 200:
            from .errors import ParseError

            raise ParseError(f"Document list {path} returned HTTP {response.status_code}.")
        documents = parse_document_rows(response.text)
        yield from documents

        pagination = parse_pagination(response.text)
        if pagination is None or page >= pagination.page_count or not documents:
            return
        if max_pages is not None and page >= max_pages:
            return
        page += 1


def list_documents(
    http: Portal24HTTP, category: int = -1, max_pages: int | None = None
) -> list[Document]:
    return list(iter_documents(http, category, max_pages=max_pages))


def list_categories(http: Portal24HTTP) -> list[DmsCategory]:
    """Parse the category tree embedded in the document list page.

    (``/dms/category/list`` is a flat table without IDs; the tree with
    IDs is embedded as DmsCategory builder scripts on the document list.)
    """
    response = http.get(DOC_LIST_PATH.format(category=-1))
    if response.status_code != 200:
        from .errors import ParseError

        raise ParseError(f"Document list returned HTTP {response.status_code}.")
    return parse_categories(response.text)


def list_objects(http: Portal24HTTP) -> list[Property]:
    response = http.get(OBJECT_SHOW_PATH)
    return parse_objects(response.text)


def list_rent_units(http: Portal24HTTP) -> list[RentUnit]:
    response = http.get(OBJECT_SHOW_PATH)
    return parse_rent_units(response.text)
