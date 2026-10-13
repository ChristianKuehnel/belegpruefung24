"""Credential resolution.

Sources, in order of precedence:

1. ``credentials:`` section of the local configuration file
   (``config.local.yaml`` — gitignored, user-managed).
2. Environment variables ``PORTAL24_EMAIL`` / ``PORTAL24_PASSWORD``.
3. OS keyring (service ``portal24``, username = email), if ``keyring``
   is installed.

Credentials are never logged and never written to any file by this
library.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .config import Portal24Config
from .errors import CredentialsError

ENV_EMAIL = "PORTAL24_EMAIL"
ENV_PASSWORD = "PORTAL24_PASSWORD"
KEYRING_SERVICE = "portal24"


@dataclass(frozen=True)
class Credentials:
    email: str
    password: str

    def __repr__(self) -> str:  # prevent accidental leakage via repr/logs
        return f"Credentials(email={self.email!r}, password=***)"


def _from_mapping(data: object) -> Credentials | None:
    if not isinstance(data, dict):
        return None
    email = data.get("email")
    password = data.get("password")
    if isinstance(email, str) and email and isinstance(password, str) and password:
        return Credentials(email=email.strip(), password=password)
    return None


def _from_env() -> Credentials | None:
    email = os.environ.get(ENV_EMAIL, "").strip()
    password = os.environ.get(ENV_PASSWORD, "")
    if email and password:
        return Credentials(email=email, password=password)
    return None


def _from_keyring(email: str) -> str | None:
    try:
        import keyring  # optional dependency
    except ImportError:
        return None
    try:
        return keyring.get_password(KEYRING_SERVICE, email)
    except Exception:  # pragma: no cover - keyring backends are environment-specific
        return None


def load_credentials(config: Portal24Config) -> Credentials:
    """Resolve credentials for the configured tenant portal."""
    creds = _from_mapping(config.raw.get("credentials"))
    if creds is not None:
        return creds

    creds = _from_env()
    if creds is not None:
        return creds

    email = os.environ.get(ENV_EMAIL, "").strip()
    if email:
        password = _from_keyring(email)
        if password:
            return Credentials(email=email, password=password)

    raise CredentialsError(
        "No credentials found. Add a 'credentials' section (email/password) to "
        "config.local.yaml, set PORTAL24_EMAIL/PORTAL24_PASSWORD, or store the "
        f"password in the OS keyring under service '{KEYRING_SERVICE}'."
    )


def store_in_keyring(creds: Credentials) -> bool:
    """Best-effort persistence into the OS keyring. Returns True on success."""
    try:
        import keyring
    except ImportError:
        return False
    try:
        keyring.set_password(KEYRING_SERVICE, creds.email, creds.password)
        return True
    except Exception:  # pragma: no cover
        return False
