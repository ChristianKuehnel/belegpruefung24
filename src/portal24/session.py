"""Session persistence.

Session cookies are stored outside the source tree in
``<session_dir>/session.json`` with ``0600`` permissions (default
``~/.config/portal24/``). The file is JSON: ``{"base_url": ..., "cookies":
{...}, "login_time": ...}``. Nothing session-related is ever written
inside a Git working tree.
"""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from .config import Portal24Config
from .errors import ConfigurationError


@dataclass
class SessionState:
    base_url: str
    cookies: dict[str, str] = field(default_factory=dict)
    login_time: str | None = None


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):  # non-POSIX filesystems
        os.chmod(path, 0o700)


def load_session(config: Portal24Config) -> SessionState | None:
    """Load a persisted session for the configured base URL, if any."""
    file = config.session_file
    if not file.is_file():
        return None
    try:
        with file.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Could not read session file {file}: {exc}") from exc

    if data.get("base_url") != config.normalized_base_url:
        return None
    cookies = data.get("cookies") or {}
    if not isinstance(cookies, dict):
        return None
    return SessionState(
        base_url=config.normalized_base_url,
        cookies={str(k): str(v) for k, v in cookies.items()},
        login_time=data.get("login_time"),
    )


def save_session(config: Portal24Config, state: SessionState) -> Path:
    file = config.session_file
    _ensure_dir(file.parent)
    payload = {
        "base_url": state.base_url,
        "cookies": state.cookies,
        "login_time": state.login_time
        or datetime.now(UTC).isoformat(timespec="seconds"),
    }
    fd = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    with contextlib.suppress(OSError):
        os.chmod(file, 0o600)
    return file


def clear_session(config: Portal24Config) -> bool:
    file = config.session_file
    if file.is_file():
        file.unlink()
        return True
    return False
