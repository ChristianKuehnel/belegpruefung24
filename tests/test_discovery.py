from __future__ import annotations

from portal24.discovery import extract_links
from tests.conftest import DASHBOARD_HTML

BASE = "https://portal.example.test"


def test_extracts_safe_links():
    links = extract_links(DASHBOARD_HTML, BASE)
    paths = [link.path for link in links]
    assert "/objects/list" in paths
    assert "/documents/category/1" in paths
    assert "/ajax/search" in paths


def test_excludes_state_changing_links():
    links = extract_links(DASHBOARD_HTML, BASE)
    paths = [link.path for link in links]
    assert "/user/auth/logout" not in paths


def test_excludes_external_and_javascript_links():
    links = extract_links(DASHBOARD_HTML, BASE)
    paths = [link.path for link in links]
    assert not any("external.example.com" in p for p in paths)
    assert not any(p.startswith("javascript") for p in paths)


def test_unsafe_markers_filtered():
    page = """
    <a href="/booking/approve/42">Freigabe</a>
    <a href="/document/upload">Upload</a>
    <a href="/documents/delete/7">Löschen</a>
    <a href="/documents/comment/8">Kommentar</a>
    <a href="/objects/view/1">Objekt</a>
    """
    paths = [link.path for link in extract_links(page, BASE)]
    assert paths == ["/objects/view/1"]


def test_entity_encoded_hrefs_decoded():
    page = '<a href="&#x2F;objects&#x2F;list">Objekte</a>'
    paths = [link.path for link in extract_links(page, BASE)]
    assert paths == ["/objects/list"]


def test_query_strings_preserved():
    page = '<a href="/documents/list?category=3&page=2">Liste</a>'
    paths = [link.path for link in extract_links(page, BASE)]
    assert paths == ["/documents/list?category=3&page=2"]


def test_deduplicates_links():
    page = '<a href="/objects/list">A</a><a href="/objects/list">B</a>'
    assert len(extract_links(page, BASE)) == 1
