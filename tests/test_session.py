from __future__ import annotations

import json
import os
from pathlib import Path

from portal24.config import Portal24Config
from portal24.session import SessionState, clear_session, load_session, save_session


def make_config(tmp_path: Path) -> Portal24Config:
    return Portal24Config(
        base_url="https://portal.example.test",
        session_dir=tmp_path / "sessiondir",
    )


def test_save_and_load_roundtrip(tmp_path: Path):
    config = make_config(tmp_path)
    state = SessionState(base_url=config.normalized_base_url, cookies={"PHPSESSID": "abc123"})
    file = save_session(config, state)

    assert file.is_file()
    assert oct(file.stat().st_mode & 0o777) == "0o600"

    loaded = load_session(config)
    assert loaded is not None
    assert loaded.cookies == {"PHPSESSID": "abc123"}
    assert loaded.login_time is not None


def test_load_returns_none_for_other_base_url(tmp_path: Path):
    config = make_config(tmp_path)
    save_session(config, SessionState(base_url=config.normalized_base_url, cookies={"a": "b"}))

    other = Portal24Config(
        base_url="https://other-tenant.example.test", session_dir=tmp_path / "sessiondir"
    )
    assert load_session(other) is None


def test_load_returns_none_when_missing(tmp_path: Path):
    assert load_session(make_config(tmp_path)) is None


def test_clear_session(tmp_path: Path):
    config = make_config(tmp_path)
    save_session(config, SessionState(base_url=config.normalized_base_url, cookies={"a": "b"}))
    assert clear_session(config) is True
    assert clear_session(config) is False
    assert load_session(config) is None


def test_session_file_never_inside_source_tree(tmp_path: Path):
    config = make_config(tmp_path)
    save_session(config, SessionState(base_url=config.normalized_base_url, cookies={"a": "b"}))
    content = json.loads(config.session_file.read_text(encoding="utf-8"))
    assert content["base_url"] == "https://portal.example.test"
    assert os.access(config.session_file, os.R_OK)
