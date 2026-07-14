from __future__ import annotations

from pathlib import Path

import pytest

from agent import corporate_policy as policy_module
from agent.corporate_path_access import (
    clear_session_path_grants,
    effective_allowed_roots,
    request_path_access,
)
from agent.corporate_policy import CorporatePolicy
from tools.terminal_tool import set_approval_callback


@pytest.fixture(autouse=True)
def reset_grants_and_callback():
    clear_session_path_grants()
    set_approval_callback(None)
    yield
    clear_session_path_grants()
    set_approval_callback(None)


def _policy(tmp_path: Path, **overrides) -> CorporatePolicy:
    values = {
        "enabled": True,
        "allowed_roots": (tmp_path / "workspace",),
        "allowed_root_parents": (tmp_path,),
        "audit_enabled": False,
    }
    values.update(overrides)
    return CorporatePolicy(**values)


def test_allow_once_grants_parent_and_retries_operation(monkeypatch, tmp_path):
    target = tmp_path / "Downloads" / "report.pdf"
    target.parent.mkdir()
    target.write_bytes(b"%PDF")
    monkeypatch.setattr(policy_module, "_policy_cache", _policy(tmp_path))
    set_approval_callback(lambda command, description, **kwargs: "once")

    error = request_path_access(target, purpose="read and process this document")

    assert error is None
    assert target in effective_allowed_roots()


def test_session_grant_reuses_permission_without_reprompt(monkeypatch, tmp_path):
    target = tmp_path / "Downloads" / "report.pdf"
    target.parent.mkdir()
    target.write_bytes(b"%PDF")
    monkeypatch.setattr(policy_module, "_policy_cache", _policy(tmp_path))
    calls = []

    def approve(command, description, **kwargs):
        calls.append(command)
        return "session"

    set_approval_callback(approve)
    assert request_path_access(target, purpose="read it") is None
    assert request_path_access(target, purpose="read it again") is None
    assert len(calls) == 1


def test_deny_reports_current_roots_and_how_to_grant(monkeypatch, tmp_path):
    target = tmp_path / "Downloads" / "report.pdf"
    monkeypatch.setattr(policy_module, "_policy_cache", _policy(tmp_path))
    set_approval_callback(lambda *args, **kwargs: "deny")

    error = request_path_access(target, purpose="read it")

    assert str(tmp_path / "workspace") in error
    assert "hermes corporate roots add" in error


def test_admin_parent_ceiling_prevents_prompt(monkeypatch, tmp_path):
    outside = tmp_path.parent / "outside" / "report.pdf"
    monkeypatch.setattr(policy_module, "_policy_cache", _policy(tmp_path))
    called = False

    def approve(*args, **kwargs):
        nonlocal called
        called = True
        return "always"

    set_approval_callback(approve)
    error = request_path_access(outside, purpose="read it")

    assert error
    assert called is False
    assert str(tmp_path) in error


def test_always_persists_user_root(monkeypatch, tmp_path):
    target = tmp_path / "Downloads" / "report.pdf"
    target.parent.mkdir()
    target.write_bytes(b"%PDF")
    config = {"product": {"mode": "corporate_local", "allowed_roots": []}}
    saved = {}
    monkeypatch.setattr(policy_module, "_policy_cache", _policy(tmp_path))
    monkeypatch.setattr("hermes_cli.config.load_config", lambda: config)
    monkeypatch.setattr(
        "hermes_cli.config.save_config",
        lambda value: saved.update(value),
    )
    monkeypatch.setattr(
        policy_module,
        "_build_policy",
        lambda: _policy(
            tmp_path,
            allowed_roots=(
                tmp_path / "workspace",
                target.parent,
            ),
        ),
    )
    set_approval_callback(lambda *args, **kwargs: "always")

    assert request_path_access(target, purpose="read it") is None
    assert str(target.parent) in saved["product"]["allowed_roots"]


def test_local_access_status_reports_roots_and_grant_options(monkeypatch, tmp_path):
    import json

    from plugins.corporate_local import _local_access_status

    monkeypatch.setattr(policy_module, "_policy_cache", _policy(tmp_path))

    result = json.loads(_local_access_status({}))

    assert str(tmp_path / "workspace") in result["allowed_roots"]
    assert str(tmp_path) in result["administrator_root_parents"]
    assert result["interactive_grants"]["session"]
    assert "hermes corporate roots add" in result["user_only_manual_command"]
    assert "agent must not execute" in result["authorization_note"].lower()
