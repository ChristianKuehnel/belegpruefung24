from __future__ import annotations

import httpx
import pytest

from portal24.client import Portal24Client
from portal24.config import Portal24Config
from portal24.credentials import Credentials
from portal24.errors import SessionExpiredError
from portal24.http import Portal24HTTP
from tests.conftest import make_portal_transport

BASE = "https://portal.example.test"


def make_client(transport: httpx.BaseTransport, session_dir) -> Portal24Client:
    config = Portal24Config(base_url=BASE, session_dir=session_dir)
    http = Portal24HTTP(BASE, transport=transport)
    return Portal24Client(config, Credentials("user@example.test", "pw"), http)


def test_login_persists_session(tmp_path):
    transport, _ = make_portal_transport()
    client = make_client(transport, tmp_path / "cfg")
    try:
        final_path = client.login()
        assert final_path == "/application/index"
        assert client.config.session_file.is_file()
    finally:
        client.close()


def test_status_authenticated(tmp_path):
    transport, _ = make_portal_transport()
    client = make_client(transport, tmp_path / "cfg")
    try:
        info = client.status()
        assert info["authenticated"] is True
        assert info["base_url"] == BASE
    finally:
        client.close()


def test_status_detects_expired_session(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(302, headers={"Location": "/user/auth/login"})
        return httpx.Response(200, text="<form></form>")

    client = make_client(httpx.MockTransport(handler), tmp_path / "cfg")
    try:
        with pytest.raises(SessionExpiredError):
            client.ensure_logged_in()
        info = client.status()
        assert info["authenticated"] is False
        assert "error" in info
    finally:
        client.close()


def test_discover_links_requires_auth(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(302, headers={"Location": "/user/auth/login"})
        return httpx.Response(200, text="<form></form>")

    client = make_client(httpx.MockTransport(handler), tmp_path / "cfg")
    try:
        with pytest.raises(SessionExpiredError):
            client.discover_links()
    finally:
        client.close()


def test_list_properties_parses_object_switcher(tmp_path):
    from tests.dms_fixtures import OBJECT_PAGE

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/portal/object/show":
            return httpx.Response(200, text=OBJECT_PAGE)
        return httpx.Response(404, text="not found")

    client = make_client(httpx.MockTransport(handler), tmp_path / "cfg")
    try:
        properties = client.list_properties()
        assert [p.id for p in properties] == ["652", "653"]
        assert properties[0].name == "Musterstr. 1"
    finally:
        client.close()
