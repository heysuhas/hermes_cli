"""Provider-neutral model tools for local desktop mail applications."""

from __future__ import annotations

import logging
import platform
import time
from typing import Any

from plugins.outlook.provider import get_provider
from plugins.outlook.providers.outlook_com import OutlookComError
from tools.registry import tool_error, tool_result


logger = logging.getLogger(__name__)

_COM_RETRY_DELAYS_SECONDS = (0.35, 0.8)
_TRANSIENT_COM_HRESULTS = {
    -2147352567,  # DISP_E_EXCEPTION; Outlook often reports temporary object-model failures this way.
    -2147418111,  # RPC_E_CALL_REJECTED; Outlook is busy/rejecting automation.
    -2147417846,  # RPC_E_SERVERCALL_RETRYLATER; retry after Outlook finishes current work.
}


MAIL_STATUS_SCHEMA = {
    "name": "mail_client_status",
    "description": "Check the locally installed desktop mail client and list configured mailbox stores.",
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

MAIL_LIST_FOLDERS_SCHEMA = {
    "name": "mail_list_folders",
    "description": (
        "List mailbox stores or folders from the local desktop mail client. "
        "Use returned store_id and entry_id values to access corporate, shared, "
        "archive, or custom folders without assuming a mailbox layout."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "store_id": {"type": "string"},
            "parent_entry_id": {"type": "string"},
            "recursive": {"type": "boolean", "default": False},
        },
        "additionalProperties": False,
    },
}

MAIL_LIST_MESSAGES_SCHEMA = {
    "name": "mail_list_messages",
    "description": (
        "List recent emails from a local desktop mail inbox or another email "
        "folder. Use for requests such as newest emails, latest mail, unread "
        "emails, recent inbox messages, or email summaries. Returns opaque "
        "entry_id and store_id locators for reading an email or drafting a response."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "store_id": {"type": "string"},
            "folder_entry_id": {"type": "string"},
            "folder": {
                "type": "string",
                "enum": ["inbox", "drafts", "sentitems", "deleteditems", "outbox", "junkemail"],
                "default": "inbox",
            },
            "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
            "unread_only": {"type": "boolean", "default": False},
            "received_after": {"type": "string", "description": "ISO-8601 timestamp."},
            "text": {
                "type": "string",
                "description": "Optional case-insensitive text matched against recent message metadata and preview.",
            },
            "scan_limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000,
                "default": 200,
                "description": "Maximum recent items inspected while applying text matching.",
            },
        },
        "additionalProperties": False,
    },
}

MAIL_GET_MESSAGE_SCHEMA = {
    "name": "mail_get_message",
    "description": (
        "Read the full body and details of one email from the local desktop "
        "mail client using the exact entry_id and store_id returned by "
        "mail_list_messages."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "entry_id": {"type": "string"},
            "store_id": {"type": "string"},
        },
        "required": ["entry_id"],
        "additionalProperties": False,
    },
}

MAIL_CREATE_DRAFT_SCHEMA = {
    "name": "mail_create_draft",
    "description": (
        "Create and save a draft in the local desktop mail application. Supports "
        "new, reply, reply-all, and forward drafts. Never sends mail."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "kind": {"type": "string", "enum": ["new", "reply", "reply_all", "forward"], "default": "new"},
            "source_entry_id": {"type": "string"},
            "source_store_id": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "body_type": {"type": "string", "enum": ["Text", "HTML"], "default": "Text"},
            "to": {"type": "array", "items": {"type": "string"}},
            "cc": {"type": "array", "items": {"type": "string"}},
            "bcc": {"type": "array", "items": {"type": "string"}},
            "attachments": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["body"],
        "additionalProperties": False,
    },
}

MAIL_UPDATE_DRAFT_SCHEMA = {
    "name": "mail_update_draft",
    "description": "Revise and save an existing unsent desktop-mail draft. Never sends mail.",
    "parameters": {
        "type": "object",
        "properties": {
            "entry_id": {"type": "string"},
            "store_id": {"type": "string"},
            "subject": {"type": "string"},
            "body": {"type": "string"},
            "body_type": {"type": "string", "enum": ["Text", "HTML"], "default": "Text"},
            "to": {"type": "array", "items": {"type": "string"}},
            "cc": {"type": "array", "items": {"type": "string"}},
            "bcc": {"type": "array", "items": {"type": "string"}},
            "attachments": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["entry_id"],
        "additionalProperties": False,
    },
}


def check_mail_client_available() -> bool:
    if platform.system() != "Windows":
        return False
    try:
        import winreg
        import pythoncom  # noqa: F401
        import win32com.client  # noqa: F401
        with winreg.OpenKey(
            winreg.HKEY_CLASSES_ROOT,
            r"Outlook.Application\CLSID",
        ):
            return True
    except ImportError:
        return False
    except OSError:
        return False


def handle_mail_status(args: dict, **_: Any) -> str:
    return _call("status")


def handle_mail_list_folders(args: dict, **_: Any) -> str:
    return _call(
        "list_folders",
        store_id=_text(args.get("store_id")),
        parent_entry_id=_text(args.get("parent_entry_id")),
        recursive=bool(args.get("recursive", False)),
    )


def handle_mail_list_messages(args: dict, **_: Any) -> str:
    return _call(
        "list_messages",
        store_id=_text(args.get("store_id")),
        folder_entry_id=_text(args.get("folder_entry_id")),
        folder=_text(args.get("folder")) or "inbox",
        limit=_bounded_int(args.get("limit"), default=20, minimum=1, maximum=50),
        unread_only=bool(args.get("unread_only", False)),
        received_after=_text(args.get("received_after")),
        text=_text(args.get("text")),
        scan_limit=_bounded_int(args.get("scan_limit"), default=200, minimum=1, maximum=1000),
    )


def handle_mail_get_message(args: dict, **_: Any) -> str:
    entry_id = _text(args.get("entry_id"))
    if not entry_id:
        return tool_error("entry_id is required")
    return _call("get_message", entry_id=entry_id, store_id=_text(args.get("store_id")))


def handle_mail_create_draft(args: dict, **_: Any) -> str:
    kind = (_text(args.get("kind")) or "new").casefold()
    body = str(args.get("body") or "")
    if not body.strip():
        return tool_error("body is required")
    if kind not in {"new", "reply", "reply_all", "forward"}:
        return tool_error("kind must be one of: new, reply, reply_all, forward")
    source_entry_id = _text(args.get("source_entry_id"))
    if kind != "new" and not source_entry_id:
        return tool_error(f"source_entry_id is required for kind='{kind}'")
    to = _addresses(args.get("to"))
    if kind == "new" and not to:
        return tool_error("to must contain at least one recipient for a new draft")
    if kind == "forward" and not to:
        return tool_error("to must contain at least one recipient for a forward draft")
    return _call(
        "create_draft",
        kind=kind,
        body=body,
        body_type=_body_type(args.get("body_type")),
        subject=str(args.get("subject") or ""),
        to=to,
        cc=_addresses(args.get("cc")),
        bcc=_addresses(args.get("bcc")),
        source_entry_id=source_entry_id,
        source_store_id=_text(args.get("source_store_id")),
        attachments=args.get("attachments"),
    )


def handle_mail_update_draft(args: dict, **_: Any) -> str:
    entry_id = _text(args.get("entry_id"))
    if not entry_id:
        return tool_error("entry_id is required")
    if not any(key in args for key in ("subject", "body", "to", "cc", "bcc", "attachments")):
        return tool_error("Provide at least one draft field to update")
    return _call(
        "update_draft",
        entry_id=entry_id,
        store_id=_text(args.get("store_id")),
        subject=str(args["subject"]) if "subject" in args else None,
        body=str(args["body"]) if "body" in args else None,
        body_type=_body_type(args.get("body_type")),
        to=_addresses(args.get("to")) if "to" in args else None,
        cc=_addresses(args.get("cc")) if "cc" in args else None,
        bcc=_addresses(args.get("bcc")) if "bcc" in args else None,
        attachments=args.get("attachments") if "attachments" in args else None,
    )


def _call(method: str, **kwargs: Any) -> str:
    attempts = len(_COM_RETRY_DELAYS_SECONDS) + 1
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            provider = get_provider()
            return tool_result(getattr(provider, method)(**kwargs))
        except OutlookComError as exc:
            return tool_error(str(exc))
        except Exception as exc:
            last_exc = exc
            if attempt < attempts and _is_transient_desktop_mail_error(exc):
                logger.info(
                    "Retrying transient desktop mail COM failure for %s "
                    "(attempt %s/%s): %s",
                    method,
                    attempt,
                    attempts,
                    _format_desktop_mail_error(exc),
                )
                time.sleep(_COM_RETRY_DELAYS_SECONDS[attempt - 1])
                continue
            break
    assert last_exc is not None
    return tool_error(
        "Desktop mail operation failed while running "
        f"{method}: {_format_desktop_mail_error(last_exc)}"
    )


def _is_transient_desktop_mail_error(exc: BaseException) -> bool:
    hresult = _com_hresult(exc)
    if hresult in _TRANSIENT_COM_HRESULTS:
        return True
    text = str(exc).casefold()
    return any(
        marker in text
        for marker in (
            "try again",
            "server call retry later",
            "call was rejected",
            "application is busy",
            "outlook is busy",
        )
    )


def _format_desktop_mail_error(exc: BaseException) -> str:
    hresult = _com_hresult(exc)
    message = _com_message(exc) or str(exc) or exc.__class__.__name__
    detail = f"{exc.__class__.__name__}"
    if hresult is not None:
        detail += f" hresult={hresult}"
    return f"{detail}: {message}"


def _com_hresult(exc: BaseException) -> int | None:
    args = getattr(exc, "args", ())
    if args and isinstance(args[0], int):
        return args[0]
    return None


def _com_message(exc: BaseException) -> str | None:
    args = getattr(exc, "args", ())
    if len(args) >= 3 and isinstance(args[2], tuple):
        details = args[2]
        for index in (2, 1):
            if len(details) > index and details[index]:
                return str(details[index])
    if len(args) >= 2 and args[1]:
        return str(args[1])
    return None


def _addresses(raw: Any) -> list[str]:
    values = raw if isinstance(raw, list) else ([] if raw is None else [raw])
    result: list[str] = []
    for value in values:
        address = str(value).strip()
        if address and address not in result:
            result.append(address)
    return result


def _text(raw: Any) -> str | None:
    value = str(raw or "").strip()
    return value or None


def _body_type(raw: Any) -> str:
    return "HTML" if str(raw or "").casefold() == "html" else "Text"


def _bounded_int(raw: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))
