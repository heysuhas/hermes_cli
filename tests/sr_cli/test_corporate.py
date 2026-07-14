"""Tests for the employee-facing corporate launcher contract."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest


@pytest.fixture
def corporate_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "sr"
    home.mkdir()
    monkeypatch.setenv("SR_HOME", str(home))
    monkeypatch.delenv("SR_CORPORATE_MODE", raising=False)
    monkeypatch.delenv("SR_CORPORATE_CONFIG_WRITE", raising=False)
    return home


def test_corporate_config_integrity_accepts_sealed_file(corporate_home: Path):
    from sr_cli.corporate import _CONFIG_DIGEST, _SETUP_MARKER, _verify_sealed_config

    config = corporate_home / "config.yaml"
    config.write_text("model:\n  provider: openai\n", encoding="utf-8")
    (corporate_home / _SETUP_MARKER).write_text("1\n", encoding="ascii")
    digest = hashlib.sha256(config.read_bytes()).hexdigest()
    (corporate_home / _CONFIG_DIGEST).write_text(digest + "\n", encoding="ascii")

    _verify_sealed_config()


def test_corporate_config_integrity_rejects_tampering(corporate_home: Path):
    from sr_cli.corporate import _CONFIG_DIGEST, _SETUP_MARKER, _verify_sealed_config

    config = corporate_home / "config.yaml"
    config.write_text("model:\n  provider: openai\n", encoding="utf-8")
    (corporate_home / _SETUP_MARKER).write_text("1\n", encoding="ascii")
    (corporate_home / _CONFIG_DIGEST).write_text("0" * 64 + "\n", encoding="ascii")

    with pytest.raises(RuntimeError, match="changed outside"):
        _verify_sealed_config()


def test_corporate_mode_blocks_config_writes(corporate_home: Path, monkeypatch: pytest.MonkeyPatch):
    from sr_cli.config import save_config

    monkeypatch.setenv("SR_CORPORATE_MODE", "1")
    with pytest.raises(PermissionError, match="managed by your organization"):
        save_config({"model": {"provider": "openai", "default": "gpt"}})


def test_corporate_entrypoint_rejects_arguments(monkeypatch: pytest.MonkeyPatch, capsys):
    from sr_cli import corporate

    monkeypatch.setattr("sys.argv", ["sr-corporate.exe", "setup"])
    with pytest.raises(SystemExit) as exc:
        corporate.main()

    assert exc.value.code == 2
    assert "does not accept command-line arguments" in capsys.readouterr().out


def test_developer_entrypoint_is_blocked_for_corporate_install(
    corporate_home: Path, monkeypatch: pytest.MonkeyPatch, capsys
):
    from sr_cli import main as sr_main

    managed_root = corporate_home / "sr-agent"
    managed_root.mkdir()
    (managed_root / ".corporate-install").write_text("1\n", encoding="ascii")
    monkeypatch.setattr("sys.argv", ["sr.exe"])

    with pytest.raises(SystemExit) as exc:
        sr_main.main()

    assert exc.value.code == 2
    assert "installed shortcut" in capsys.readouterr().out
