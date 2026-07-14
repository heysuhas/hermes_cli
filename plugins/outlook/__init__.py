"""Local desktop-mail integration with classic Outlook as the first adapter."""

from __future__ import annotations

from plugins.outlook.cli import outlook_command, register_cli
from plugins.outlook.tools import (
    MAIL_CREATE_DRAFT_SCHEMA,
    MAIL_GET_MESSAGE_SCHEMA,
    MAIL_LIST_FOLDERS_SCHEMA,
    MAIL_LIST_MESSAGES_SCHEMA,
    MAIL_STATUS_SCHEMA,
    MAIL_UPDATE_DRAFT_SCHEMA,
    check_mail_client_available,
    handle_mail_create_draft,
    handle_mail_get_message,
    handle_mail_list_folders,
    handle_mail_list_messages,
    handle_mail_status,
    handle_mail_update_draft,
)


_TOOLS = (
    ("mail_client_status", MAIL_STATUS_SCHEMA, handle_mail_status, "📮"),
    ("mail_list_folders", MAIL_LIST_FOLDERS_SCHEMA, handle_mail_list_folders, "🗂️"),
    ("mail_list_messages", MAIL_LIST_MESSAGES_SCHEMA, handle_mail_list_messages, "📬"),
    ("mail_get_message", MAIL_GET_MESSAGE_SCHEMA, handle_mail_get_message, "📨"),
    ("mail_create_draft", MAIL_CREATE_DRAFT_SCHEMA, handle_mail_create_draft, "📝"),
    ("mail_update_draft", MAIL_UPDATE_DRAFT_SCHEMA, handle_mail_update_draft, "✏️"),
)


def register(ctx) -> None:
    for name, schema, handler, emoji in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset="desktop_mail",
            schema=schema,
            handler=handler,
            check_fn=check_mail_client_available,
            emoji=emoji,
        )
    ctx.register_cli_command(
        name="outlook",
        help="Inspect the local classic Outlook integration",
        setup_fn=register_cli,
        handler_fn=outlook_command,
        description=(
            "Provider-neutral desktop mail tools backed by classic Outlook COM. "
            "Tools can read mail and save drafts, but cannot send."
        ),
    )

