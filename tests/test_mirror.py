from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from portal24.errors import SyncError
from portal24.http import Portal24HTTP
from portal24.mirror import Mirror, MirrorOptions, sanitize_filename, validate_destination
from tests.dms_fixtures import make_document_page, make_row

BASE = "https://portal.example.test"

DOC_101 = b"%PDF-1.4 synthetic-document-101"
DOC_102 = b"%PDF-1.4 synthetic-document-102"


def make_transport(released: dict[str, str] | None = None, duplicate: bool = False):
    """Simulate: category tree page + per-category lists + downloads."""
    released = released or {"101": "30.07.2026, 09:57:57", "102": "09.10.2026, 11:56:35"}
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path

        if path == "/dms/document/download/101":
            return httpx.Response(200, content=DOC_101, headers={"Content-Type": "application/pdf"})
        if path == "/dms/document/download/102":
            return httpx.Response(200, content=DOC_102, headers={"Content-Type": "application/pdf"})

        if path == "/dms/document/list/-1":
            rows = [
                make_row("101", "09.2025_Muster.pdf", released=released["101"]),
                make_row("102", "Mietvertrag.pdf", category="Allgemein", released=released["102"]),
            ]
            return httpx.Response(200, text=make_document_page(rows, total=2))

        if path == "/dms/document/list/1":
            rows = [make_row("101", "09.2025_Muster.pdf", released=released["101"])]
            if duplicate:
                rows.append(make_row("102", "Mietvertrag.pdf", category="Allgemein",
                                     released=released["102"]))
            return httpx.Response(200, text=make_document_page(rows, total=len(rows),
                                                               with_categories=False))
        if path == "/dms/document/list/2":
            rows = [make_row("102", "Mietvertrag.pdf", category="Allgemein",
                             released=released["102"])]
            return httpx.Response(200, text=make_document_page(rows, total=1,
                                                               with_categories=False))
        if path == "/dms/document/list/3":
            return httpx.Response(200, text=make_document_page([], total=0, with_categories=False))

        return httpx.Response(404, text="not found")

    return httpx.MockTransport(handler), calls


def make_mirror(tmp_path, transport, **kwargs) -> Mirror:
    http = Portal24HTTP(BASE, transport=transport)
    return Mirror(http, MirrorOptions(destination=tmp_path / "mirror", **kwargs))


def test_first_sync_downloads_all(tmp_path):
    transport, _ = make_transport()
    mirror = make_mirror(tmp_path, transport)
    result = mirror.sync()

    assert result.complete
    assert result.enumerated == 2
    assert result.downloaded == 2
    assert result.skipped_unchanged == 0
    assert result.failed == 0

    dest = tmp_path / "mirror"
    f101 = dest / "documents" / "Belegprüfung" / "101_09.2025_Muster.pdf"
    f102 = dest / "documents" / "Allgemein" / "102_Mietvertrag.pdf"
    assert f101.read_bytes() == DOC_101
    assert f102.read_bytes() == DOC_102

    manifest = json.loads((dest / "manifests" / "files.json").read_text())
    entry = manifest["files"]["101"]
    assert entry["sha256"] == hashlib.sha256(DOC_101).hexdigest()
    assert entry["local_path"] == "documents/Belegprüfung/101_09.2025_Muster.pdf"
    assert entry["source_url"].startswith(BASE)

    report = json.loads((dest / "sync-report.json").read_text())
    assert report["complete"] is True
    assert report["enumerated"] == 2


def test_second_sync_is_idempotent(tmp_path):
    transport, _ = make_transport()
    mirror = make_mirror(tmp_path, transport)
    mirror.sync()

    transport2, _ = make_transport()
    mirror2 = make_mirror(tmp_path, transport2)
    result = mirror2.sync()

    assert result.downloaded == 0
    assert result.skipped_unchanged == 2
    assert result.complete


def test_changed_release_triggers_redownload(tmp_path):
    transport, _ = make_transport()
    make_mirror(tmp_path, transport).sync()

    changed = {"101": "31.07.2026, 09:57:57", "102": "09.10.2026, 11:56:35"}
    transport2, _ = make_transport(released=changed)
    result = make_mirror(tmp_path, transport2).sync()

    assert result.downloaded == 1
    assert result.skipped_unchanged == 1


def test_dry_run_writes_nothing(tmp_path):
    transport, _ = make_transport()
    mirror = make_mirror(tmp_path, transport, dry_run=True)
    result = mirror.sync()

    assert result.downloaded == 2
    assert result.skipped_unchanged == 0
    assert not (tmp_path / "mirror").exists()


def test_dry_run_after_sync_reports_unchanged(tmp_path):
    make_mirror(tmp_path, make_transport()[0]).sync()
    result = make_mirror(tmp_path, make_transport()[0], dry_run=True).sync()

    assert result.downloaded == 0
    assert result.skipped_unchanged == 2


def test_failed_download_removes_partial_file(tmp_path, monkeypatch):
    transport, _ = make_transport()
    mirror = make_mirror(tmp_path, transport)

    class _BrokenResponse:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def iter_bytes(self, chunk_size):
            yield b"%PDF"
            raise httpx.ConnectError("connection dropped mid-download")

    def broken_stream(path, **kwargs):
        return _BrokenResponse()

    monkeypatch.setattr(mirror.http, "stream", broken_stream)
    result = mirror.sync()

    assert result.failed == 2
    assert not [
        p for p in (tmp_path / "mirror").rglob("*.part")
    ], "partial .part files must be cleaned up"


def test_duplicate_document_downloaded_once(tmp_path):
    transport, _ = make_transport(duplicate=True)
    result = make_mirror(tmp_path, transport).sync()

    assert result.enumerated == 2
    assert result.downloaded == 2
    manifest = json.loads(
        (tmp_path / "mirror" / "manifests" / "files.json").read_text()
    )
    assert len(manifest["files"]) == 2
    assert manifest["files"]["102"]["references"], "duplicate reference recorded"


def test_destination_inside_git_tree_rejected(tmp_path):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    with pytest.raises(SyncError):
        validate_destination(tmp_path / "repo" / "mirror")


def test_destination_outside_git_tree_accepted(tmp_path):
    resolved = validate_destination(tmp_path / "mirror")
    assert resolved == (tmp_path / "mirror").resolve()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("simple.pdf", "simple.pdf"),
        ("a/b\\c:d.pdf", "a_b_c_d.pdf"),
        ("  spaced  name  .pdf", "spaced name.pdf"),
        ("...", "unnamed"),
        ("x" * 300 + ".pdf", ("x" * 146) + ".pdf"),
    ],
)
def test_sanitize_filename(raw: str, expected: str):
    assert sanitize_filename(raw) == expected
