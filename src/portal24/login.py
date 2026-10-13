"""Login / logout flow (verified against the public login page, v3.26.0).

Flow:
1. ``GET /user/auth/login`` — bootstraps the session cookie and renders
   the login form, which contains a hidden ``type`` field holding a
   per-page 32-character token.
2. ``POST /user/auth/login?today=`` with form fields ``email``,
   ``password``, ``type`` (token), ``submit``.
3. Success is indicated by a redirect away from the login page; failure
   re-renders the login page (optionally with an error message).
"""

from __future__ import annotations

import html
import re

from .credentials import Credentials
from .errors import AuthenticationError, ParseError
from .http import Portal24HTTP

LOGIN_PATH = "/user/auth/login"
LOGIN_ACTION = "/user/auth/login?today="
LOGOUT_PATH = "/user/auth/logout"

_HIDDEN_TYPE_RE = re.compile(
    r"<input[^>]*\bname=[\"']type[\"'][^>]*\bvalue=[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
_HIDDEN_TYPE_RE_ALT = re.compile(
    r"<input[^>]*\bvalue=[\"']([^\"']+)[\"'][^>]*\bname=[\"']type[\"']",
    re.IGNORECASE,
)
_ERROR_MARKUP_RE = re.compile(
    r"class=[\"'][^\"']*(?:error|alert-danger|alert-error)[^\"']*[\"'][^>]*>([^<]{3,120})<",
    re.IGNORECASE,
)


def extract_login_token(page_html: str) -> str:
    """Extract the hidden ``type`` anti-replay token from the login page."""
    decoded = html.unescape(page_html)
    for pattern in (_HIDDEN_TYPE_RE, _HIDDEN_TYPE_RE_ALT):
        match = pattern.search(decoded)
        if match:
            return match.group(1)
    raise ParseError("Could not find the hidden 'type' token on the login page.")


def _extract_error_message(page_html: str) -> str | None:
    decoded = html.unescape(page_html)
    match = _ERROR_MARKUP_RE.search(decoded)
    if match:
        return match.group(1).strip()
    return None


def fetch_login_token(http: Portal24HTTP) -> str:
    response = http.get(LOGIN_PATH)
    if response.status_code != 200:
        raise AuthenticationError(f"Login page returned HTTP {response.status_code}.")
    return extract_login_token(response.text)


def login(http: Portal24HTTP, credentials: Credentials) -> str:
    """Authenticate. Returns the final (post-redirect) URL path on success."""
    token = fetch_login_token(http)
    response = http.post_auth(
        LOGIN_ACTION,
        data={
            "email": credentials.email,
            "password": credentials.password,
            "type": token,
            "submit": "Login",
        },
    )
    final_path = response.url.path
    if response.status_code in (401, 403):
        raise AuthenticationError(f"Login rejected with HTTP {response.status_code}.")
    if "/user/auth/login" in final_path:
        message = _extract_error_message(response.text)
        raise AuthenticationError(
            "Login failed: the server returned the login page again."
            + (f" Server message: {message}" if message else " Check email/password.")
        )
    return final_path


def logout(http: Portal24HTTP) -> None:
    """Log out (permitted lifecycle operation). Tries POST then GET."""
    try:
        http.post_auth(LOGOUT_PATH, data={})
    except Exception:
        http.get(LOGOUT_PATH)
