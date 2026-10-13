from __future__ import annotations

import pytest

from portal24.config import Portal24Config
from portal24.credentials import Credentials, load_credentials
from portal24.errors import CredentialsError


def make_config(raw: dict) -> Portal24Config:
    return Portal24Config(base_url="https://portal.example.test", raw=raw)


def test_credentials_from_config():
    config = make_config({"credentials": {"email": "user@example.test", "password": "pw"}})
    creds = load_credentials(config)
    assert creds.email == "user@example.test"
    assert creds.password == "pw"


def test_credentials_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PORTAL24_EMAIL", "env@example.test")
    monkeypatch.setenv("PORTAL24_PASSWORD", "envpw")
    creds = load_credentials(make_config({}))
    assert creds.email == "env@example.test"
    assert creds.password == "envpw"


def test_credentials_config_beats_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PORTAL24_EMAIL", "env@example.test")
    monkeypatch.setenv("PORTAL24_PASSWORD", "envpw")
    config = make_config({"credentials": {"email": "cfg@example.test", "password": "cfgpw"}})
    creds = load_credentials(config)
    assert creds.email == "cfg@example.test"


def test_credentials_missing_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PORTAL24_EMAIL", raising=False)
    monkeypatch.delenv("PORTAL24_PASSWORD", raising=False)
    with pytest.raises(CredentialsError):
        load_credentials(make_config({}))


def test_credentials_incomplete_mapping_ignored(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PORTAL24_EMAIL", raising=False)
    monkeypatch.delenv("PORTAL24_PASSWORD", raising=False)
    config = make_config({"credentials": {"email": "only@example.test"}})
    with pytest.raises(CredentialsError):
        load_credentials(config)


def test_repr_never_leaks_password():
    creds = Credentials(email="user@example.test", password="supersecret")
    assert "supersecret" not in repr(creds)
    assert "user@example.test" in repr(creds)
