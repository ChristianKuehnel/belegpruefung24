"""Read-only HTTP transport for Portal24.

Safety model
------------
* Only ``GET`` and ``HEAD`` requests are ever issued.
* ``POST`` is permitted exclusively for the explicit authentication
  allowlist (login/logout) — everything else raises
  :class:`~portal24.errors.ReadOnlyViolationError` before any network
  traffic.
* Logging redacts cookies, authorization headers, and sensitive query
  parameters.
* Transient failures (connection errors, 5xx) are retried with bounded
  exponential backoff.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .errors import NetworkError, ReadOnlyViolationError

logger = logging.getLogger("portal24.http")

USER_AGENT = "portal24-python/0.1 (unofficial read-only client)"

#: Paths that may receive POST requests (authentication lifecycle only).
AUTH_POST_ALLOWLIST = frozenset({"/user/auth/login", "/user/auth/logout"})

_SENSITIVE_QUERY_KEYS = frozenset(
    {"password", "passwd", "token", "signature", "sig", "key", "secret", "auth"}
)
_SENSITIVE_HEADER_KEYS = frozenset({"cookie", "set-cookie", "authorization", "proxy-authorization"})


def redact_query(url: str) -> str:
    """Mask sensitive query parameters in a URL string."""
    if "?" not in url:
        return url
    base, query = url.split("?", 1)
    parts = []
    for pair in query.split("&"):
        if not pair:
            continue
        key, _, _value = pair.partition("=")
        if key.lower() in _SENSITIVE_QUERY_KEYS:
            parts.append(f"{key}=***)")
        else:
            parts.append(pair)
    return f"{base}?{'&'.join(parts)}"


def redact_headers(headers: dict[str, str] | httpx.Headers) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in dict(headers).items():
        out[key] = "***" if key.lower() in _SENSITIVE_HEADER_KEYS else value
    return out


class _RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
            for key in ("cookie", "authorization", "set-cookie"):
                lowered = message.lower()
                if f"{key}:" in lowered:
                    import re

                    message = re.sub(
                        rf"({key}:\s*)(.+)",
                        lambda m: m.group(1) + "***",
                        message,
                        flags=re.IGNORECASE,
                    )
            record.msg = message
            record.args = ()
        except Exception:  # pragma: no cover - logging must never break requests
            pass
        return True


logger.addFilter(_RedactingFilter())


class Portal24HTTP:
    """A small, policy-enforcing wrapper around :class:`httpx.Client`."""

    def __init__(
        self,
        base_url: str,
        cookies: dict[str, str] | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_retries = max(1, max_retries)
        self.backoff_base = backoff_base
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "de-DE,de;q=0.9,en;q=0.6"},
            transport=transport,
        )
        if cookies:
            for name, value in cookies.items():
                self._client.cookies.set(name, value)

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> Portal24HTTP:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    @property
    def cookies(self) -> dict[str, str]:
        return {cookie.name: cookie.value for cookie in self._client.cookies.jar}

    # -- policy ------------------------------------------------------------

    def _check_policy(self, method: str, path: str) -> None:
        method = method.upper()
        if method in ("GET", "HEAD"):
            return
        clean_path = path.split("?", 1)[0]
        if method == "POST" and clean_path in AUTH_POST_ALLOWLIST:
            return
        raise ReadOnlyViolationError(
            f"Refusing to issue {method} {path}: this client is strictly read-only. "
            "Only GET/HEAD and the authentication allowlist are permitted."
        )

    # -- transport ---------------------------------------------------------

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        self._check_policy(method, path)
        last_error: Exception | None = None
        response: httpx.Response | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._client.request(
                    method, path, params=params, data=data, headers=headers
                )
            except httpx.TransportError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    delay = self.backoff_base * (2 ** (attempt - 1))
                    logger.warning("Network error on %s %s (%s); retry %d in %.1fs",
                                   method, redact_query(path), exc, attempt, delay)
                    time.sleep(delay)
                    continue
                raise NetworkError(f"Request {method} {redact_query(path)} failed: {exc}") from exc

            if response.status_code >= 500 and attempt < self.max_retries:
                delay = self.backoff_base * (2 ** (attempt - 1))
                logger.warning("Server error %d on %s %s; retry %d in %.1fs",
                               response.status_code, method, redact_query(path), attempt, delay)
                time.sleep(delay)
                continue
            break

        if response is None:
            raise NetworkError(f"Request {method} {redact_query(path)} failed: {last_error}")
        if response.status_code >= 500:
            raise NetworkError(
                f"Request {method} {redact_query(path)} failed with HTTP {response.status_code} "
                f"after {self.max_retries} attempt(s)."
            )
        logger.debug("%s %s -> %d", method, redact_query(path), response.status_code)
        return response

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def get_json(self, path: str, **kwargs: Any) -> Any:
        response = self.get(path, **kwargs)
        try:
            return response.json()
        except ValueError as exc:
            from .errors import ParseError

            raise ParseError(f"Expected JSON from {path}, got {response.status_code}") from exc

    def stream(self, path: str, **kwargs: Any):
        """Stream a GET response body (for file downloads)."""
        self._check_policy("GET", path)
        return self._client.stream("GET", path, **kwargs)

    def post_auth(self, path: str, data: dict[str, Any]) -> httpx.Response:
        """POST restricted to the authentication allowlist."""
        return self.request("POST", path, data=data)
