"""High-level client facade."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import Portal24Config, load_config
from .credentials import Credentials, load_credentials
from .discovery import Link, discover
from .dms import (
    TICKET_LIST_PATH,
    list_categories,
    list_documents,
    list_objects,
    list_rent_units,
    parse_tickets,
)
from .errors import AuthenticationError, SessionExpiredError
from .http import Portal24HTTP
from .login import LOGIN_PATH
from .login import login as _login
from .login import logout as _logout
from .mirror import Mirror, MirrorOptions
from .models import DmsCategory, Document, Property, RentUnit, SyncResult, Ticket
from .session import SessionState, clear_session, load_session, save_session


class Portal24Client:
    """Strictly read-only client for an Immoware24 Portal24 tenant portal.

    Example:
        from portal24 import Portal24Client

        with Portal24Client.from_local_credentials() as client:
            client.login()
            print(client.status())
    """

    def __init__(
        self,
        config: Portal24Config,
        credentials: Credentials,
        http: Portal24HTTP,
    ) -> None:
        self.config = config
        self.credentials = credentials
        self.http = http

    # -- construction ------------------------------------------------------

    @classmethod
    def from_local_credentials(cls, config_path: str | None = None) -> Portal24Client:
        config = load_config(config_path)
        credentials = load_credentials(config)
        session = load_session(config)
        cookies = session.cookies if session else None
        http = Portal24HTTP(config.normalized_base_url, cookies=cookies)
        return cls(config, credentials, http)

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> Portal24Client:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self.http.close()

    # -- authentication ----------------------------------------------------

    def login(self) -> str:
        """Authenticate and persist the session outside the source tree."""
        final_path = _login(self.http, self.credentials)
        state = SessionState(base_url=self.config.normalized_base_url, cookies=self.http.cookies)
        save_session(self.config, state)
        return final_path

    def logout(self) -> None:
        _logout(self.http)
        clear_session(self.config)

    def ensure_logged_in(self) -> None:
        """Raise :class:`SessionExpiredError` if the session is invalid."""
        response = self.http.get("/")
        if LOGIN_PATH in response.url.path:
            raise SessionExpiredError(
                "Session is not valid (redirected to login). Run 'portal24 login'."
            )

    def status(self) -> dict[str, Any]:
        """Report configuration and session state without leaking secrets."""
        info: dict[str, Any] = {
            "base_url": self.config.normalized_base_url,
            "config_source": str(self.config.source_path) if self.config.source_path else None,
            "credentials_source": "local-config" if self.credentials else "missing",
            "session_file": str(self.config.session_file),
            "session_stored": self.config.session_file.is_file(),
            "authenticated": False,
        }
        try:
            self.ensure_logged_in()
            info["authenticated"] = True
        except AuthenticationError as exc:
            info["error"] = str(exc)
        return info

    # -- discovery ---------------------------------------------------------

    def discover_links(self, start_paths: tuple[str, ...] = ("/",)) -> list[Link]:
        self.ensure_logged_in()
        return discover(self.http, start_paths)

    def list_properties(self) -> list[Property]:
        """All objects (properties/WEGs) accessible to the user."""
        self.ensure_logged_in()
        return list_objects(self.http)

    def list_rent_units(self) -> list[RentUnit]:
        """All rent units (administrative units) of the user."""
        self.ensure_logged_in()
        return list_rent_units(self.http)

    def list_categories(self) -> list[DmsCategory]:
        """The DMS category tree with server-side document counts."""
        self.ensure_logged_in()
        return list_categories(self.http)

    def list_documents(self, category: int = -1, max_pages: int | None = None) -> list[Document]:
        """All documents, optionally restricted to one category id."""
        self.ensure_logged_in()
        return list_documents(self.http, category, max_pages=max_pages)

    def list_tickets(self) -> list[Ticket]:
        """Support tickets from the communicator module."""
        self.ensure_logged_in()
        response = self.http.get(TICKET_LIST_PATH)
        if response.status_code != 200:
            from .errors import ParseError

            raise ParseError(f"Ticket list returned HTTP {response.status_code}.")
        return parse_tickets(response.text)

    # -- mirroring ---------------------------------------------------------

    def sync(
        self,
        destination: str | Path | None = None,
        dry_run: bool = False,
    ) -> SyncResult:
        """Mirror all accessible documents and metadata to ``destination``.

        The destination must be outside any Git working tree.
        """
        self.ensure_logged_in()
        dest = Path(destination) if destination else self.config.mirror_destination
        options = MirrorOptions(destination=dest, dry_run=dry_run)
        mirror = Mirror(self.http, options)
        result = mirror.sync()
        if not dry_run:
            self._write_metadata(mirror)
        return result

    def _write_metadata(self, mirror: Mirror) -> None:
        """Write machine-readable metadata exports next to the mirror."""
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        objects = self.list_properties()
        rent_units = self.list_rent_units()
        categories = self.list_categories()
        documents = self.list_documents()

        account = mirror.destination / "account.json"
        account.write_text(
            json.dumps(
                {
                    "provenance": "client-generated from server-rendered pages",
                    "base_url": self.http.base_url,
                    "retrieved_at": stamp,
                    "objects": [asdict(o) for o in objects],
                    "rent_units": [asdict(r) for r in rent_units],
                    "categories": [
                        {"id": c.id, "name": c.name, "path": c.path, "count": c.count,
                         "children": [ch.id for ch in c.children]}
                        for c in categories
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        doc_file = mirror.destination / "documents.json"
        doc_file.write_text(
            json.dumps(
                {
                    "provenance": "client-generated from the DMS document list "
                    "(server-rendered HTML); not a native server export",
                    "base_url": self.http.base_url,
                    "retrieved_at": stamp,
                    "total": len(documents),
                    "documents": [asdict(d) for d in documents],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
