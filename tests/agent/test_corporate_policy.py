from __future__ import annotations

import pytest
import yaml
from types import SimpleNamespace

from agent import corporate_policy as policy_module


@pytest.fixture(autouse=True)
def reset_policy():
    policy_module.reset_policy_cache()
    yield
    policy_module.reset_policy_cache()


def test_admin_policy_is_a_ceiling_and_user_can_only_restrict(monkeypatch, tmp_path):
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "allowed_tools": ["terminal", "read_file", "write_file"],
                "allowed_plugins": ["outlook", "corporate_office"],
                "allowed_root_parents": [str(tmp_path)],
                "terminal": {"denied_patterns": [r"\breg\s+add\b"]},
            }
        ),
        encoding="utf-8",
    )
    selected_root = tmp_path / "project"
    monkeypatch.setattr(policy_module, "_program_data_policy_path", lambda: policy_path)
    monkeypatch.setattr(
        policy_module,
        "_load_user_config",
        lambda: {
            "product": {
                "mode": "corporate_local",
                "allowed_roots": [str(selected_root)],
                "allowed_tools": ["terminal", "read_file", "web_search"],
                "allowed_plugins": ["outlook", "browser"],
            }
        },
    )

    policy = policy_module.get_corporate_policy(refresh=True)

    assert policy.allowed_tools == frozenset({"terminal", "read_file"})
    assert policy.allowed_plugins == frozenset({"outlook"})
    assert policy.allows_path(selected_root / "report.docx")
    assert not policy.allows_path(tmp_path.parent / "outside.docx")
    assert policy.terminal_command_error("reg add HKCU\\Software\\Example")
    outside = tmp_path.parent / "outside.txt"
    assert policy.terminal_referenced_path_error(f'type "{outside}"')


def test_network_policy_allows_loopback_and_blocks_public(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_PRODUCT_MODE", "corporate_local")
    monkeypatch.setattr(policy_module, "_load_user_config", lambda: {})
    monkeypatch.setattr(
        policy_module, "_program_data_policy_path", lambda: tmp_path / "missing.yaml"
    )

    policy = policy_module.get_corporate_policy(refresh=True)

    assert policy.allows_url("http://127.0.0.1:11434/v1")
    assert policy.allows_url("http://localhost:8765/v1/catalog")
    assert not policy.allows_url("https://example.com")
    assert not policy.allows_url("https://public-broker.example/v1/catalog")
    assert policy.terminal_command_error("curl https://example.com")
    assert policy.terminal_command_error("python -m pip install requests")
    self_grant_error = policy.terminal_command_error(
        r"hermes corporate roots add C:\Users\test\Downloads"
    )
    assert self_grant_error
    assert "cannot grant itself" in self_grant_error
    local_install = "python -m pip install --no-index C:\\approved\\tool.whl"
    assert policy.terminal_command_error(local_install) is None
    assert policy.terminal_approval_reason(local_install)


def test_corporate_tool_schema_is_narrow(monkeypatch, tmp_path):
    monkeypatch.setenv("HERMES_PRODUCT_MODE", "corporate_local")
    monkeypatch.setenv("TERMINAL_CWD", str(tmp_path))
    monkeypatch.setattr(policy_module, "_load_user_config", lambda: {})
    monkeypatch.setattr(
        policy_module, "_program_data_policy_path", lambda: tmp_path / "missing.yaml"
    )
    policy_module.get_corporate_policy(refresh=True)

    from hermes_cli.plugins import discover_plugins
    from model_tools import _clear_tool_defs_cache, get_tool_definitions

    discover_plugins(force=True)
    _clear_tool_defs_cache()
    names = {
        item["function"]["name"]
        for item in get_tool_definitions(quiet_mode=True)
    }

    assert {"terminal", "skills_list", "document_extract"} <= names
    assert not {
        "web_search",
        "web_extract",
        "browser_navigate",
        "execute_code",
        "tool_search",
    } & names


def test_file_tools_enforce_approved_roots(monkeypatch, tmp_path):
    import json

    from agent.corporate_policy import CorporatePolicy
    from tools.file_tools import read_file_tool, search_tool, write_file_tool

    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("business data", encoding="utf-8")
    monkeypatch.setattr(
        policy_module,
        "_policy_cache",
        CorporatePolicy(enabled=True, allowed_roots=(allowed,), audit_enabled=False),
    )

    for result in (
        read_file_tool(str(outside)),
        write_file_tool(str(outside), "changed"),
        search_tool("business", path=str(tmp_path)),
    ):
        assert "outside" in json.loads(result)["error"].lower()


def test_corporate_prompt_is_compact_and_local(monkeypatch, tmp_path):
    from agent.corporate_policy import CorporatePolicy
    from agent.system_prompt import build_system_prompt_parts

    monkeypatch.setattr(
        policy_module,
        "_policy_cache",
        CorporatePolicy(enabled=True, allowed_roots=(tmp_path,), audit_enabled=False),
    )
    agent = SimpleNamespace(
        model="qwen3:9b",
        _memory_store=None,
        _memory_enabled=False,
        _user_profile_enabled=False,
    )

    prompt = build_system_prompt_parts(agent)

    assert "Hermes Corporate Local Assistant" in prompt["stable"]
    assert "Direct public-internet access is prohibited" in prompt["stable"]
    assert "browser automation" in prompt["stable"]
    assert "Policy: corporate_local/" in prompt["volatile"]
