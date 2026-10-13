"""Shared fixtures: synthetic Portal24 pages and a mock transport."""

from __future__ import annotations

import httpx

LOGIN_PAGE_HTML = """
<html><body>
<form method="POST" action="/user/auth/login?today=" name="AbstractForm" id="AbstractForm">
  <input type="text" name="email" placeholder="E-Mail">
  <input type="password" name="password" id="zabc123def4567890">
  <input type="hidden" name="type" value="SyntheticToken0123456789ABCDEF012345">
  <input type="submit" name="submit" value="Login">
</form>
</body></html>
"""

LOGIN_PAGE_ENTITY_ENCODED = (
    "<html><body>"
    "<form method=\"POST\" action=\"&#x2F;user&#x2F;auth&#x2F;login&#x3F;today&#x3D;\">"
    "<input type=\"hidden\" name=\"type\" value=\"EncodedToken0123456789ABCDEF012345\">"
    "</form></body></html>"
)

LOGIN_PAGE_ERROR_HTML = """
<html><body>
<div class="alert alert-danger">E-Mail oder Passwort ist falsch.</div>
<form method="POST" action="/user/auth/login?today=">
  <input type="hidden" name="type" value="RetryToken0123456789ABCDEF01234567">
</form>
</body></html>
"""

DASHBOARD_HTML = """
<html><body>
<a href="/objects/list">Objekte</a>
<a href="/documents/category/1">Dokumente</a>
<a href="/user/auth/logout">Abmelden</a>
<a href="https://external.example.com/page">Extern</a>
<a href="javascript:void(0)">JS</a>
<a data-url="/ajax/search" href="#">Suche</a>
</body></html>
"""


def make_portal_transport(fail_login: bool = False):
    """Return (MockTransport, call log) simulating the verified login flow."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        path = request.url.path
        if path == "/user/auth/login" and request.method == "GET":
            return httpx.Response(
                200,
                text=LOGIN_PAGE_HTML,
                headers={"Set-Cookie": "PHPSESSID=synthetic_session; path=/"},
            )
        if path == "/user/auth/login" and request.method == "POST":
            body = request.content.decode("utf-8")
            if fail_login or "password=wrong" in body:
                return httpx.Response(200, text=LOGIN_PAGE_ERROR_HTML)
            return httpx.Response(302, headers={"Location": "/application/index"})
        if path == "/application/index":
            return httpx.Response(200, text="<html><body>dashboard</body></html>")
        if path == "/":
            return httpx.Response(200, text=DASHBOARD_HTML)
        return httpx.Response(404, text="not found")

    return httpx.MockTransport(handler), calls
