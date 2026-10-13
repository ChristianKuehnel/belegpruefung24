"""Local mirror / synchronization engine.

Design (see docs/PROJECT_SPEC.md §7):
* Reproduce the server hierarchy: category tree (with nesting) under
  ``documents/``, objects/rent-units metadata under ``objects/``.
* Stable document IDs prefix every filename, which also resolves
  duplicate-name and case-folding collisions.
* Manifests map server resources to local paths with size, SHA-256,
  server release timestamp, and download state.
* Incremental: a document is re-downloaded only when the server release
  timestamp changed or the local file hash no longer matches.
* Non-destructive: local files are never deleted.
* Destinations inside a Git working tree are rejected.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import httpx

from .dms import DOC_DOWNLOAD_PATH, list_documents
from .errors import Portal24Error, SyncError
from .http import Portal24HTTP
from .models import DmsCategory, Document, SyncResult

MANIFEST_DIR = "manifests"
FILES_MANIFEST = "files.json"
SYNC_REPORT = "sync-report.json"
DOCUMENTS_DIR = "documents"
OBJECTS_DIR = "objects"


def sanitize_filename(name: str, max_length: int = 150) -> str:
    """Make a server-provided filename safe for local storage."""
    cleaned = name.replace("/", "_").replace("\\", "_")
    cleaned = re.sub(r'[<>:"|?*\x00-\x1f]', "_", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
    cleaned = re.sub(r"\s+(\.\w{1,10}$)", r"\1", cleaned)
    if not cleaned:
        return "unnamed"
    if len(cleaned) > max_length:
        stem, dot, ext = cleaned.rpartition(".")
        if dot and len(ext) <= 10:
            cleaned = stem[: max_length - len(ext) - 1] + "." + ext
        else:
            cleaned = cleaned[:max_length]
    return cleaned


def validate_destination(destination: Path) -> Path:
    """Resolve the destination and refuse Git working trees."""
    resolved = destination.expanduser().resolve()
    probe = resolved
    while True:
        if (probe / ".git").exists():
            raise SyncError(
                f"Refusing to mirror into {resolved}: it is inside the Git "
                f"working tree {probe}. Private data must stay outside the repository."
            )
        if probe == probe.parent:
            break
        probe = probe.parent
    return resolved


@dataclass
class MirrorOptions:
    destination: Path
    dry_run: bool = False
    max_pages_per_category: int | None = None


@dataclass
class _ManifestEntry:
    id: str
    name: str
    category: str | None
    category_path: str | None
    size: int | None
    sha256: str | None
    released: str | None
    local_path: str
    source_url: str
    downloaded_at: str | None
    references: list[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Mirror:
    def __init__(self, http: Portal24HTTP, options: MirrorOptions) -> None:
        self.http = http
        self.options = options
        self.destination = validate_destination(options.destination)
        self.manifest_path = self.destination / MANIFEST_DIR / FILES_MANIFEST
        self._manifest: dict[str, _ManifestEntry] = {}
        if self.manifest_path.is_file():
            try:
                raw = json.loads(self.manifest_path.read_text(encoding="utf-8"))
                for doc_id, entry in raw.get("files", {}).items():
                    self._manifest[doc_id] = _ManifestEntry(**entry)
            except (json.JSONDecodeError, TypeError) as exc:
                raise SyncError(f"Corrupt manifest {self.manifest_path}: {exc}") from exc

    # -- enumeration -------------------------------------------------------

    def _enumerate(self) -> tuple[list[tuple[Document, DmsCategory | None]], dict[str, list[str]]]:
        """Enumerate documents per category so the category is unambiguous.

        Returns (pairs, duplicate_refs): pairs are (document, category) with
        the same document id kept only once (first category wins);
        duplicate_refs maps a document id to the additional category paths
        where it also appeared.
        """
        from .dms import list_categories

        categories = list_categories(self.http)
        flat: list[DmsCategory] = []

        def collect(nodes: list[DmsCategory]) -> None:
            for node in nodes:
                flat.append(node)
                collect(node.children)

        collect(categories)

        assigned: dict[str, tuple[Document, DmsCategory | None]] = {}
        duplicate_refs: dict[str, list[str]] = {}
        for category in flat:
            try:
                docs = list_documents(
                    self.http, category.id, max_pages=self.options.max_pages_per_category
                )
            except Portal24Error:
                raise
            except Exception as exc:  # noqa: BLE001 - wrap unexpected parser errors
                raise SyncError(f"Failed to enumerate category {category.id}: {exc}") from exc
            for doc in docs:
                if doc.id in assigned:
                    _, prev_category = assigned[doc.id]
                    prev_path = prev_category.path if prev_category else "?"
                    ref = f"{category.path} (duplicate of {prev_path})"
                    duplicate_refs.setdefault(doc.id, []).append(ref)
                    continue
                assigned[doc.id] = (doc, category)
        return list(assigned.values()), duplicate_refs

    # -- download ----------------------------------------------------------

    def _target_path(self, doc: Document, category: DmsCategory | None) -> Path:
        category_path = category.path if category else (doc.category or "Unkategorisiert")
        parts = [sanitize_filename(part) for part in category_path.split("/") if part]
        filename = f"{doc.id}_{sanitize_filename(doc.name)}"
        return self.destination / DOCUMENTS_DIR / Path(*parts) / filename

    def _is_unchanged(self, doc: Document, entry: _ManifestEntry | None) -> bool:
        if entry is None:
            return False
        if doc.released and entry.released and doc.released != entry.released:
            return False
        local = self.destination / entry.local_path
        if not local.is_file():
            return False
        if entry.sha256:
            return hashlib.sha256(local.read_bytes()).hexdigest() == entry.sha256
        return doc.size is not None and local.stat().st_size == doc.size

    def _download(self, doc: Document, target: Path) -> tuple[int, str]:
        tmp = target.with_name(target.name + ".part")
        digest = hashlib.sha256()
        size = 0
        try:
            with self.http.stream(
                doc.download_url or DOC_DOWNLOAD_PATH.format(id=doc.id)
            ) as response:
                if response.status_code != 200:
                    raise SyncError(
                        f"Download of document {doc.id} failed with "
                        f"HTTP {response.status_code}."
                    )
                with tmp.open("wb") as handle:
                    for chunk in response.iter_bytes(65536):
                        handle.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
            os.replace(tmp, target)
        except SyncError:
            raise
        except httpx.HTTPError as exc:
            raise SyncError(f"Download of document {doc.id} failed: {exc}") from exc
        finally:
            with contextlib.suppress(OSError):
                if tmp.exists():
                    tmp.unlink()
        return size, digest.hexdigest()

    # -- sync --------------------------------------------------------------

    def sync(self) -> SyncResult:
        result = SyncResult(destination=str(self.destination))
        if not self.options.dry_run:
            (self.destination / MANIFEST_DIR).mkdir(parents=True, exist_ok=True)

        try:
            pairs, duplicate_refs = self._enumerate()
        except SyncError as exc:
            result.errors.append(str(exc))
            self._write_report(result)
            return result

        result.enumerated = len(pairs)
        for doc, category in pairs:
            target = self._target_path(doc, category)
            entry = self._manifest.get(doc.id)
            rel_path = target.relative_to(self.destination).as_posix()

            if self._is_unchanged(doc, entry):
                result.skipped_unchanged += 1
                continue

            if self.options.dry_run:
                result.downloaded += 1
                continue

            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                size, sha256 = self._download(doc, target)
            except (SyncError, OSError) as exc:
                result.failed += 1
                result.errors.append(f"document {doc.id} ({doc.name}): {exc}")
                continue

            result.downloaded += 1
            references = list(duplicate_refs.get(doc.id, []))
            if entry and entry.references:
                for ref in entry.references:
                    if ref not in references:
                        references.append(ref)
            self._manifest[doc.id] = _ManifestEntry(
                id=doc.id,
                name=doc.name,
                category=doc.category,
                category_path=category.path if category else None,
                size=size,
                sha256=sha256,
                released=doc.released,
                local_path=rel_path,
                source_url=f"{self.http.base_url}{doc.download_url}",
                downloaded_at=_now(),
                references=references,
            )

        if not self.options.dry_run:
            self._write_manifest()
        self._write_report(result)
        return result

    # -- persistence -------------------------------------------------------

    def _write_manifest(self) -> None:
        payload = {
            "generated_at": _now(),
            "base_url": self.http.base_url,
            "files": {doc_id: asdict(entry) for doc_id, entry in sorted(self._manifest.items())},
        }
        self.manifest_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def _write_report(self, result: SyncResult) -> None:
        if self.options.dry_run:
            return
        payload = {
            "generated_at": _now(),
            "base_url": self.http.base_url,
            "destination": str(self.destination),
            "dry_run": False,
            "enumerated": result.enumerated,
            "downloaded": result.downloaded,
            "skipped_unchanged": result.skipped_unchanged,
            "failed": result.failed,
            "duplicates": sum(len(e.references) for e in self._manifest.values()),
            "errors": result.errors,
            "complete": result.complete,
        }
        (self.destination / SYNC_REPORT).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
