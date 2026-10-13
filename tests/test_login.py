from __future__ import annotations

import pytest

from portal24.credentials import Credentials
from portal24.errors import AuthenticationError, ParseError
from portal24.http import Portal24HTTP
from portal24.login import extract_login_token, fetch_login_token, login
from tests.conftest import (
    LOGIN_PAGE_ENTITY_ENCODED,
    LOGIN_PAGE_HTML,
    make_portal_transport,
)

BASE = "https://portal.example.test"


def test_extract_token_plain():
    assert extract_login_token(LOGIN_PAGE_HTML) == "SyntheticToken0123456789ABCDEF012345"


def test_extract_token_entity_encoded():
    assert extract_login_token(LOGIN_PAGE_ENTITY_ENCODED) == "EncodedToken0123456789ABCDEF012345"


def test_extract_token_reversed_attribute_order():
    page = '<form><input type="hidden" value="RevTok0123456789ABCDEF0123456789" name="type"></form>'
    assert extract_login_token(page) == "RevTok0123456789ABCDEF0123456789"


def test_extract_token_missing_raises():
    with pytest.raises(ParseError):
        extract_login_token("<html><body>no form</body></html>")


def test_login_success_follows_redirect():
    transport, calls = make_portal_transport()
    with Portal24HTTP(BASE, transport=transport) as http:
        final_path = login(http, Credentials("user@example.test", "correct-horse"))
    assert final_path == "/application/index"

    post = [c for c in calls if c.method == "POST"][0]
    body = post.content.decode("utf-8")
    assert "email=user%40example.test" in body
    assert "password=correct-horse" in body
    assert "type=SyntheticToken0123456789ABCDEF012345" in body
    assert post.url.path == "/user/auth/login"
    assert post.url.query.decode() == "today="


def test_login_failure_stays_on_login_page():
    transport, _ = make_portal_transport()
    with Portal24HTTP(BASE, transport=transport) as http, pytest.raises(
        AuthenticationError
    ) as excinfo:
        login(http, Credentials("user@example.test", "wrong"))
    assert "login page again" in str(excinfo.value)


def test_login_failure_reports_server_message():
    transport, _ = make_portal_transport(fail_login=True)
    with Portal24HTTP(BASE, transport=transport) as http, pytest.raises(
        AuthenticationError
    ) as excinfo:
        login(http, Credentials("user@example.test", "anything"))
    assert "E-Mail oder Passwort ist falsch" in str(excinfo.value)


def test_fetch_login_token_uses_session_bootstrap():
    transport, calls = make_portal_transport()
    with Portal24HTTP(BASE, transport=transport) as http:
        token = fetch_login_token(http)
    assert token == "SyntheticToken0123456789ABCDEF012345"
    assert calls[0].method == "GET"
    assert calls[0].url.path == "/user/auth/login"
