from __future__ import annotations

from pathlib import Path

import pytest

from portal24.config import load_config
from portal24.errors import ConfigurationError


def write_config(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "config.local.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_load_config_normalizes_base_url(tmp_path: Path):
    path = write_config(tmp_path, "base_url: https://portal.example.test/\n")
    config = load_config(path)
    assert config.normalized_base_url == "https://portal.example.test"
    assert config.source_path == path


def test_load_config_adds_scheme(tmp_path: Path):
    path = write_config(tmp_path, "base_url: portal.example.test\n")
    config = load_config(path)
    assert config.normalized_base_url == "https://portal.example.test"


def test_load_config_missing_base_url(tmp_path: Path):
    path = write_config(tmp_path, "mirror:\n  destination: /tmp/x\n")
    with pytest.raises(ConfigurationError):
        load_config(path)


def test_load_config_missing_file(tmp_path: Path):
    with pytest.raises(ConfigurationError):
        load_config(tmp_path / "nope.yaml")


def test_load_config_invalid_yaml(tmp_path: Path):
    path = write_config(tmp_path, "base_url: [unclosed\n")
    with pytest.raises(ConfigurationError):
        load_config(path)


def test_mirror_destination_expanded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    path = write_config(tmp_path, "base_url: https://x.test\n")
    config = load_config(path)
    assert config.mirror_destination == home / "data" / "portal24-mirror"
