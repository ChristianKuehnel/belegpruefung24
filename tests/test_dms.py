from __future__ import annotations

from portal24.dms import (
    parse_categories,
    parse_document_rows,
    parse_objects,
    parse_pagination,
    parse_rent_units,
    parse_tickets,
)
from tests.dms_fixtures import (
    CATEGORY_SCRIPTS,
    OBJECT_PAGE,
    TICKET_PAGE,
    make_document_page,
    make_row,
)


def test_parse_document_rows():
    page = make_document_page(
        [
            make_row("101", "09.2025_Musterstr. 1.pdf", status="neu", size="4 MB",
                     released="30.07.2026, 09:57:57", category="Belegprüfung"),
            make_row("102", "Mietvertrag Muster.pdf", size="140 KB",
                     downloaded="09.10.2026, 17:16:30", category="Allgemein"),
        ],
        total=2,
    )
    docs = parse_document_rows(page)
    assert len(docs) == 2
    first, second = docs
    assert first.id == "101"
    assert first.name == "09.2025_Musterstr. 1.pdf"
    assert first.status == "neu"
    assert first.size == 4 * 1024**2
    assert first.released == "30.07.2026, 09:57:57"
    assert first.downloaded is None
    assert first.category == "Belegprüfung"
    assert first.download_url == "/dms/document/download/101"
    assert second.id == "102"
    assert second.status == "gelesen"
    assert second.downloaded == "09.10.2026, 17:16:30"
    assert second.category == "Allgemein"


def test_parse_document_rows_empty():
    assert parse_document_rows("<html><body></body></html>") == []


def test_parse_pagination():
    page = make_document_page([make_row("1", "a.pdf")], total=43, page_count=2)
    info = parse_pagination(page)
    assert info is not None
    assert (info.first, info.last, info.total, info.page_count) == (1, 43, 43, 2)


def test_parse_pagination_absent():
    assert parse_pagination("<html></html>") is None


def test_parse_categories_tree():
    page = make_document_page([make_row("1", "a.pdf")], total=1)
    categories = parse_categories(page)
    assert [c.id for c in categories] == [1, 2]
    assert categories[0].path == "Belegprüfung"
    assert categories[1].path == "Allgemein"
    child = categories[1].children[0]
    assert child.id == 3
    assert child.path == "Allgemein/Unterordner"
    assert child.parent_id == 2


def test_parse_objects():
    properties = parse_objects(OBJECT_PAGE)
    assert [(p.id, p.name, p.address) for p in properties] == [
        ("652", "Musterstr. 1", "Musterstr. 1, Musterstadt"),
        ("653", "Beispielweg 2", "Beispielweg 2, Beispielstadt"),
    ]


def test_parse_rent_units():
    units = parse_rent_units(OBJECT_PAGE)
    assert [(u.id, u.name, u.kind, u.since) for u in units] == [
        ("3071", "WHG 1", "Wohnung", "01.01.2010")
    ]


def test_parse_tickets():
    tickets = parse_tickets(TICKET_PAGE)
    assert len(tickets) == 1
    ticket = tickets[0]
    assert ticket.id == "136"
    assert ticket.number == "TSP#136"
    assert ticket.title == "Wasser undicht"
    assert ticket.status == "in Bearbeitung"
    assert ticket.created == "03.02.2026, 12:40:24"
    assert ticket.url == "/communicator/ticket/show/136"


def test_category_scripts_standalone():
    categories = parse_categories(CATEGORY_SCRIPTS)
    assert len(categories) == 2
    assert categories[1].children[0].id == 3
