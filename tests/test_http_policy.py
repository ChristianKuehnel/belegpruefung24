from __future__ import annotations

import httpx
import pytest

from portal24.errors import NetworkError, ReadOnlyViolationError
from portal24.http import Portal24HTTP, redact_headers, redact_query


def test_get_is_allowed():
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text="ok"))
    with Portal24HTTP("https://portal.example.test", transport=transport) as http:
        response = http.get("/application/index")
        assert response.status_code == 200


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_non_auth_writes_are_blocked(method: str):
    with Portal24HTTP("https://portal.example.test") as http, pytest.raises(
        ReadOnlyViolationError
    ):
        http.request(method, "/document/123")


def test_post_to_non_allowlisted_path_blocked():
    with Portal24HTTP("https://portal.example.test") as http, pytest.raises(
        ReadOnlyViolationError
    ):
        http.request("POST", "/booking/approve/1", data={})


def test_post_to_login_allowlisted():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user/auth/login":
            return httpx.Response(302, headers={"Location": "/application/index"})
        return httpx.Response(200, text="ok")

    with Portal24HTTP(
        "https://portal.example.test", transport=httpx.MockTransport(handler)
    ) as http:
        response = http.post_auth("/user/auth/login", data={"email": "a@b.test"})
        assert response.status_code == 200


def test_stream_is_get_only():
    with Portal24HTTP("https://portal.example.test") as http, pytest.raises(
        ReadOnlyViolationError
    ):
        http._check_policy("POST", "/documents/download/1")


def test_redact_query_masks_sensitive_params():
    url = "https://x.test/p?password=secret&token=abc&signature=xyz&id=1"
    redacted = redact_query(url)
    assert "secret" not in redacted
    assert "abc" not in redacted
    assert "xyz" not in redacted
    assert "id=1" in redacted


def test_redact_headers_masks_cookies_and_auth():
    redacted = redact_headers({"Cookie": "PHPSESSID=abc", "Authorization": "Bearer t", "X-Ok": "1"})
    assert redacted["Cookie"] == "***"
    assert redacted["Authorization"] == "***"
    assert redacted["X-Ok"] == "1"


def test_retry_on_500_then_success():
    state = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["count"] += 1
        if state["count"] < 3:
            return httpx.Response(502, text="bad gateway")
        return httpx.Response(200, text="ok")

    with Portal24HTTP(
        "https://portal.example.test", transport=httpx.MockTransport(handler), backoff_base=0.01
    ) as http:
        response = http.get("/application/index")
        assert response.status_code == 200
        assert state["count"] == 3


def test_retry_exhaustion_raises_network_error():
    state = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["count"] += 1
        return httpx.Response(503, text="unavailable")

    with Portal24HTTP(
        "https://portal.example.test",
        transport=httpx.MockTransport(handler),
        max_retries=2,
        backoff_base=0.01,
    ) as http:
        with pytest.raises(NetworkError):
            http.get("/application/index")
        assert state["count"] == 2


def test_4xx_is_not_retried():
    state = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["count"] += 1
        return httpx.Response(404, text="nope")

    with Portal24HTTP(
        "https://portal.example.test", transport=httpx.MockTransport(handler), backoff_base=0.01
    ) as http:
        response = http.get("/missing")
        assert response.status_code == 404
        assert state["count"] == 1
