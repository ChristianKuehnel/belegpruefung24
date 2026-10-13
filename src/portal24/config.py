"""Local configuration loading.

Configuration is read from, in order of precedence:

1. the path given explicitly (argument or ``PORTAL24_CONFIG``),
2. a ``config.local.yaml`` found by walking up from the working directory,
3. ``~/.config/portal24/config.yaml``.

The local file is expected to be gitignored; it may contain the tenant
base URL and credentials. No configuration is ever written into the
source tree by this library.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .errors import ConfigurationError

ENV_CONFIG_PATH = "PORTAL24_CONFIG"
LOCAL_FILENAMES = ("config.local.yaml", "config.local.yml")
USER_CONFIG_DIR = Path.home() / ".config" / "portal24"
USER_FILENAMES = ("config.yaml", "config.yml")

DEFAULT_MIRROR_DESTINATION = "~/data/portal24-mirror"


@dataclass(frozen=True)
class Portal24Config:
    """Resolved, non-secret-ish runtime configuration."""

    base_url: str
    mirror_destination: Path = Path(DEFAULT_MIRROR_DESTINATION)
    session_dir: Path | None = None
    source_path: Path | None = None
    raw: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    @property
    def normalized_base_url(self) -> str:
        url = self.base_url.strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return url

    @property
    def resolved_session_dir(self) -> Path:
        return Path(self.session_dir) if self.session_dir else USER_CONFIG_DIR

    @property
    def session_file(self) -> Path:
        return self.resolved_session_dir / "session.json"


def _candidate_paths(start: Path | None = None) -> list[Path]:
    candidates: list[Path] = []
    env = os.environ.get(ENV_CONFIG_PATH)
    if env:
        candidates.append(Path(env).expanduser())
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        for name in LOCAL_FILENAMES:
            candidates.append(directory / name)
    for name in USER_FILENAMES:
        candidates.append(USER_CONFIG_DIR / name)
    return candidates


def find_config_file(start: Path | None = None) -> Path | None:
    for candidate in _candidate_paths(start):
        if candidate.is_file():
            return candidate
    return None


def _parse(raw: dict[str, Any], source: Path) -> Portal24Config:
    base_url = raw.get("base_url") or raw.get("url")
    if not base_url or not isinstance(base_url, str):
        raise ConfigurationError(f"Configuration file {source} lacks a 'base_url' entry.")

    mirror = Path(str(raw.get("mirror", {}).get("destination", DEFAULT_MIRROR_DESTINATION)))
    mirror = mirror.expanduser()

    session_dir = raw.get("session_dir")
    session_dir = Path(str(session_dir).expanduser()) if session_dir else None

    return Portal24Config(
        base_url=base_url,
        mirror_destination=mirror,
        session_dir=session_dir,
        source_path=source,
        raw=raw,
    )


def load_config(path: Path | str | None = None) -> Portal24Config:
    """Load configuration; raise :class:`ConfigurationError` if unavailable."""
    if path is not None:
        candidate = Path(path).expanduser()
        if not candidate.is_file():
            raise ConfigurationError(f"Config file not found: {candidate}")
        return _parse(_read_yaml(candidate), candidate)

    found = find_config_file()
    if found is None:
        raise ConfigurationError(
            "No configuration file found. Create config.local.yaml with a 'base_url' "
            f"entry, or set {ENV_CONFIG_PATH}."
        )
    return _parse(_read_yaml(found), found)


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"Configuration root in {path} must be a mapping.")
    return data
