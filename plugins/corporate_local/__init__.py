"""Corporate-local runtime hooks and operator commands."""

from __future__ import annotations

import hashlib
from typing import Any

from agent.corporate_events import (
    ComplianceEvent,
    OperationalEvent,
    record_compliance,
    record_operational,
)
from agent.corporate_policy import get_corporate_policy
from plugins.corporate_local.cli import corporate_command, register_cli
from tools.registry import tool_result


LOCAL_ACCESS_STATUS_SCHEMA = {
    "name": "local_access_status",
    "description": (
        "Show the local folders Hermes can currently access, administrator "
        "root-selection limits, and how the user can grant another folder."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}


def _local_access_status(args: dict, **kwargs: Any) -> str:
    from agent.corporate_path_access import effective_allowed_roots

    policy = get_corporate_policy()
    return tool_result(
        {
            "corporate_local": policy.enabled,
            "allowed_roots": [
                str(path) for path in effective_allowed_roots(policy)
            ],
            "administrator_root_parents": [
                str(path) for path in policy.allowed_root_parents
            ],
            "interactive_grants": {
                "once": "brief grant for the requested path",
                "session": "folder access for the current Hermes session",
                "always": "persist folder under product.allowed_roots",
                "deny": "keep access blocked",
            },
            "user_only_manual_command": "hermes corporate roots add <folder>",
            "authorization_note": (
                "This command may only be run by the user in a separate shell; "
                "the agent must not execute it."
            ),
        }
    )


def _resource_from_args(args: Any) -> str:
    if not isinstance(args, dict):
        return ""
    for key in ("path", "output_path", "workdir", "source_entry_id", "entry_id"):
        value = args.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def on_post_tool_call(**kwargs: Any) -> None:
    policy = get_corporate_policy()
    if not policy.enabled:
        return
    tool_name = str(kwargs.get("tool_name") or "")
    args = kwargs.get("args")
    result = kwargs.get("result")
    success = not (
        isinstance(result, str)
        and any(marker in result.lower() for marker in ('"success":false', '"error":'))
    )
    duration = kwargs.get("duration") or kwargs.get("duration_seconds") or 0
    try:
        duration_ms = int(float(duration) * 1000)
    except (TypeError, ValueError):
        duration_ms = 0
    record_operational(
        OperationalEvent(
            event_type="tool_call",
            capability=tool_name.split("_", 1)[0] if tool_name else "unknown",
            success=success,
            duration_ms=duration_ms,
            tool_name=tool_name,
        )
    )
    command_hash = ""
    if tool_name == "terminal" and isinstance(args, dict):
        command = str(args.get("command") or "")
        if command:
            command_hash = hashlib.sha256(command.encode("utf-8")).hexdigest()
    record_compliance(
        ComplianceEvent(
            event_type="tool_call",
            action=tool_name,
            success=success,
            resource=_resource_from_args(args),
            command_hash=command_hash,
            tool_name=tool_name,
        )
    )


def on_post_approval_response(**kwargs: Any) -> None:
    if not get_corporate_policy().enabled:
        return
    record_compliance(
        ComplianceEvent(
            event_type="approval",
            action=str(kwargs.get("pattern_key") or "approval"),
            success=str(kwargs.get("choice") or "") not in {"deny", "timeout"},
            approval=str(kwargs.get("choice") or ""),
        )
    )


def register(ctx) -> None:
    ctx.register_tool(
        name="local_access_status",
        toolset="corporate_local",
        schema=LOCAL_ACCESS_STATUS_SCHEMA,
        handler=_local_access_status,
        check_fn=lambda: get_corporate_policy().enabled,
        emoji="🔐",
    )
    ctx.register_hook("post_tool_call", on_post_tool_call)
    ctx.register_hook("post_approval_response", on_post_approval_response)
    ctx.register_cli_command(
        name="corporate",
        help="Inspect corporate-local policy or manage Windows Firewall rules",
        setup_fn=register_cli,
        handler_fn=corporate_command,
        description="Corporate-local policy, broker, audit, and firewall diagnostics.",
    )
