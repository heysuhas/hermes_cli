from __future__ import annotations

from agent.agent_runtime_helpers import (
    build_compact_tool_recovery_request,
    looks_like_false_tool_capability_denial,
    looks_like_unexecuted_tool_action,
    parse_forced_textual_tool_call,
    select_recovery_tool,
)


class _Agent:
    valid_tool_names = {"mail_list_messages", "read_file"}

    @staticmethod
    def _strip_think_blocks(value: str) -> str:
        return value


def test_detects_generic_promised_action_without_tool_call():
    messages = [{"role": "user", "content": "Do the requested operation"}]
    assert looks_like_unexecuted_tool_action(
        _Agent(),
        "I'll use the available integration to read the records.",
        messages,
        0,
    )


def test_detects_simulated_command_after_action_commitment():
    messages = [{"role": "user", "content": "Do the requested operation"}]
    assert looks_like_unexecuted_tool_action(
        _Agent(),
        "I'll use the relevant skill now.\n\n```\nfake command --limit 2\n```",
        messages,
        0,
    )


def test_does_not_classify_benign_promise_as_tool_action():
    messages = [{"role": "user", "content": "Explain this briefly"}]
    assert not looks_like_unexecuted_tool_action(
        _Agent(),
        "I'll be concise: the answer is 42.",
        messages,
        0,
    )


def test_does_not_recover_after_current_turn_already_used_tool():
    messages = [
        {"role": "user", "content": "Read the records"},
        {"role": "assistant", "tool_calls": [{"id": "c1"}]},
        {"role": "tool", "tool_call_id": "c1", "content": "{}"},
    ]
    assert not looks_like_unexecuted_tool_action(
        _Agent(),
        "I'll use another tool to summarize it.",
        messages,
        0,
    )


def test_detects_false_capability_denial():
    assert looks_like_false_tool_capability_denial(
        "I don't have access to your inbox or an appropriate email tool."
    )


def test_detects_false_direct_access_denial():
    assert looks_like_false_tool_capability_denial(
        "I don't have direct access to your personal email account. "
        "I can't actually read your inbox."
    )


def test_detects_false_capability_wording():
    assert looks_like_false_tool_capability_denial(
        "I don't have the capability to read your personal emails."
    )


def test_does_not_classify_normal_tool_failure_explanation_as_denial():
    assert not looks_like_false_tool_capability_denial(
        "The mail tool returned a COM permission error."
    )


def test_ignores_tool_results_from_previous_turn():
    messages = [
        {"role": "user", "content": "Earlier request"},
        {"role": "assistant", "tool_calls": [{"id": "old"}]},
        {"role": "tool", "tool_call_id": "old", "content": "{}"},
        {"role": "assistant", "content": "Earlier answer"},
        {"role": "user", "content": "New request"},
    ]
    assert looks_like_unexecuted_tool_action(
        _Agent(),
        "Let me check that now.",
        messages,
        4,
    )


def _tool(name: str, description: str) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": {}},
        },
    }


def test_recovery_selector_uses_live_schema_semantics():
    defs = [
        _tool("mail_list_messages", "List newest recent emails from an inbox"),
        _tool("read_file", "Read a local file from disk"),
        _tool("web_search", "Search the public web"),
    ]
    assert (
        select_recovery_tool(defs, "read my last two recent emails")
        == "mail_list_messages"
    )


def test_recovery_selector_declines_ambiguous_request():
    defs = [
        _tool("search_files", "Search files"),
        _tool("web_search", "Search the web"),
    ]
    assert select_recovery_tool(defs, "search") is None


def test_compact_recovery_request_contains_only_selected_live_schema():
    defs = [
        _tool("mail_list_messages", "List recent emails"),
        _tool("read_file", "Read a local file"),
    ]
    request = build_compact_tool_recovery_request(
        defs,
        "mail_list_messages",
        "read my last two recent emails",
    )
    assert request is not None
    assert [tool["function"]["name"] for tool in request["tools"]] == [
        "mail_list_messages"
    ]
    assert request["messages"][-1] == {
        "role": "user",
        "content": "read my last two recent emails",
    }


def test_compact_recovery_request_rejects_missing_tool():
    assert build_compact_tool_recovery_request([], "missing", "do it") is None


def test_parses_textual_rendering_of_exact_forced_tool():
    parsed = parse_forced_textual_tool_call(
        "I'll do that.\n\ntool:mail_list_messages(limit=2)\n:response",
        "mail_list_messages",
    )
    assert parsed == {
        "name": "mail_list_messages",
        "arguments": {"limit": 2},
    }


def test_parses_bare_function_rendering_and_filters_unknown_argument():
    parsed = parse_forced_textual_tool_call(
        "I'll retrieve them.\nmail_list_messages(limit=2, order='-date')",
        "mail_list_messages",
        allowed_arguments={"folder", "limit"},
    )
    assert parsed == {
        "name": "mail_list_messages",
        "arguments": {"limit": 2},
    }


def test_parses_multiline_fenced_function_rendering():
    parsed = parse_forced_textual_tool_call(
        "I'll fetch them.\n\n```python\n"
        "mail_list_messages(\n"
        '    folder="INBOX",\n'
        "    limit=2,\n"
        "    flags=None\n"
        ")\n"
        "```",
        "mail_list_messages",
        allowed_arguments={"folder", "limit"},
    )
    assert parsed == {
        "name": "mail_list_messages",
        "arguments": {"folder": "INBOX", "limit": 2},
    }


def test_parses_json_rendering_and_normalizes_schema_argument_alias():
    parsed = parse_forced_textual_tool_call(
        '```json\n{"tool_name":"mail_list_messages","arguments":{"count":2}}\n```',
        "mail_list_messages",
        allowed_arguments={"folder", "limit"},
    )
    assert parsed == {
        "name": "mail_list_messages",
        "arguments": {"limit": 2},
    }


def test_parses_uri_rendering_of_exact_forced_tool():
    parsed = parse_forced_textual_tool_call(
        "[tool](hermes_tools://mail_list_messages) "
        "hermes_tools://mail_list_messages",
        "mail_list_messages",
        allowed_arguments={"folder", "limit"},
    )
    assert parsed == {
        "name": "mail_list_messages",
        "arguments": {},
    }


def test_parses_bracketed_call_and_normalizes_page_size():
    parsed = parse_forced_textual_tool_call(
        '[Calling mail_list_messages: {"page": 1, "page_size": 2}]',
        "mail_list_messages",
        allowed_arguments={"folder", "limit"},
    )
    assert parsed == {
        "name": "mail_list_messages",
        "arguments": {"limit": 2},
    }


def test_rejects_textual_call_for_different_tool():
    assert (
        parse_forced_textual_tool_call(
            "tool:terminal(command='whoami')",
            "mail_list_messages",
        )
        is None
    )


def test_rejects_executable_textual_arguments():
    assert (
        parse_forced_textual_tool_call(
            "tool:mail_list_messages(limit=run_code())",
            "mail_list_messages",
        )
        is None
    )


def test_parses_fenced_cli_rendering_and_filters_unknown_schema_args():
    parsed = parse_forced_textual_tool_call(
        "```bash\nmail_list_messages limit=2 sort_by=received\n```",
        "mail_list_messages",
        allowed_arguments={"folder", "limit"},
    )
    assert parsed == {
        "name": "mail_list_messages",
        "arguments": {"limit": 2},
    }


def test_salvages_matching_flags_from_wrong_cli_name_without_executing_it():
    parsed = parse_forced_textual_tool_call(
        "```bash\nhimalaya list_messages --limit 2 --account work\n```",
        "mail_list_messages",
        allowed_arguments={"folder", "limit"},
    )
    assert parsed == {
        "name": "mail_list_messages",
        "arguments": {"limit": 2},
    }
