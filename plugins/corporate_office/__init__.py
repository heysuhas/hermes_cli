"""Corporate-local document and Microsoft Office tools."""

from __future__ import annotations

from plugins.corporate_office.tools import TOOL_DEFINITIONS


def _corporate_mode_enabled() -> bool:
    from agent.corporate_policy import is_corporate_mode

    return is_corporate_mode()


def register(ctx) -> None:
    for name, schema, handler, emoji in TOOL_DEFINITIONS:
        ctx.register_tool(
            name=name,
            toolset="corporate_office",
            schema=schema,
            handler=handler,
            check_fn=_corporate_mode_enabled,
            emoji=emoji,
        )
