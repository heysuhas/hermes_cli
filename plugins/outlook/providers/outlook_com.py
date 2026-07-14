"""Classic Outlook for Windows adapter using the Outlook Object Model."""

from __future__ import annotations

import contextlib
import platform
import re
import threading
from datetime import datetime, timezone
from typing import Any, Iterator

from plugins.outlook.providers.base import DesktopMailProvider


OL_MAIL = 43
OL_MAIL_ITEM = 0
OL_FOLDER_DELETED_ITEMS = 3
OL_FOLDER_SENT_MAIL = 5
OL_FOLDER_INBOX = 6
OL_FOLDER_OUTBOX = 4
OL_FOLDER_DRAFTS = 16
OL_FOLDER_JUNK = 23

DEFAULT_FOLDERS = {
    "deleteditems": OL_FOLDER_DELETED_ITEMS,
    "drafts": OL_FOLDER_DRAFTS,
    "inbox": OL_FOLDER_INBOX,
    "junkemail": OL_FOLDER_JUNK,
    "outbox": OL_FOLDER_OUTBOX,
    "sentitems": OL_FOLDER_SENT_MAIL,
}

PR_SMTP_ADDRESS = "http://schemas.microsoft.com/mapi/proptag/0x39FE001E"
_OUTLOOK_COM_LOCK = threading.RLock()
_INVISIBLE_PREVIEW_CHARS_RE = re.compile("[\u034f\u061c\u180e\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]")
_PREVIEW_URL_RE = re.compile(r"<?https?://\S+>?", re.IGNORECASE)


class OutlookComError(RuntimeError):
    """Raised when classic Outlook COM automation cannot complete."""


def _safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


class OutlookComProvider(DesktopMailProvider):
    provider_id = "outlook_com"

    @contextlib.contextmanager
    def _session(self) -> Iterator[tuple[Any, Any]]:
        if platform.system() != "Windows":
            raise OutlookComError("Outlook COM automation requires Windows.")
        try:
            import pythoncom
            import win32com.client
        except ImportError as exc:
            raise OutlookComError(
                "Outlook COM automation requires pywin32 on Windows."
            ) from exc

        pythoncom.CoInitialize()
        try:
            with _OUTLOOK_COM_LOCK:
                try:
                    application = win32com.client.Dispatch("Outlook.Application")
                    namespace = application.GetNamespace("MAPI")
                except Exception as exc:
                    raise OutlookComError(
                        "Could not connect to classic Outlook. Ensure classic Outlook "
                        "is installed and a mail profile is configured."
                    ) from exc
                yield application, namespace
        finally:
            pythoncom.CoUninitialize()

    def status(self) -> dict[str, Any]:
        with self._session() as (application, namespace):
            stores = self._stores(namespace)
            return {
                "available": True,
                "provider": self.provider_id,
                "application": getattr(application, "Name", "Microsoft Outlook"),
                "version": getattr(application, "Version", None),
                "profile": getattr(namespace, "CurrentProfileName", None),
                "stores": stores,
            }

    def list_folders(
        self,
        *,
        store_id: str | None = None,
        parent_entry_id: str | None = None,
        recursive: bool = False,
    ) -> dict[str, Any]:
        with self._session() as (_, namespace):
            if parent_entry_id:
                parent = self._get_folder(namespace, parent_entry_id, store_id)
                resolved_store_id = store_id or self._folder_store_id(parent)
                folders = self._folder_children(
                    parent,
                    resolved_store_id,
                    recursive=recursive,
                )
            elif store_id:
                root = namespace.GetStoreFromID(store_id).GetRootFolder()
                folders = self._folder_children(root, store_id, recursive=recursive)
            else:
                return {"provider": self.provider_id, "stores": self._stores(namespace)}
            return {"provider": self.provider_id, "folders": folders}

    def list_messages(
        self,
        *,
        store_id: str | None = None,
        folder_entry_id: str | None = None,
        folder: str = "inbox",
        limit: int = 20,
        unread_only: bool = False,
        received_after: str | None = None,
        text: str | None = None,
        scan_limit: int = 200,
    ) -> dict[str, Any]:
        with self._session() as (_, namespace):
            target = self._resolve_folder(
                namespace,
                store_id=store_id,
                folder_entry_id=folder_entry_id,
                folder=folder,
            )
            resolved_store_id = store_id or self._folder_store_id(target)
            items = target.Items
            try:
                items.Sort("[ReceivedTime]", True)
            except Exception:
                items.Sort("[CreationTime]", True)

            restrictions: list[str] = []
            if unread_only:
                restrictions.append("[Unread] = True")
            if received_after:
                parsed = _parse_utc(received_after)
                local_value = parsed.astimezone().strftime("%m/%d/%Y %I:%M %p")
                restrictions.append(f"[ReceivedTime] >= '{local_value}'")
            if restrictions:
                items = items.Restrict(" AND ".join(restrictions))

            needle = (text or "").casefold().strip()
            messages: list[dict[str, Any]] = []
            scanned = 0
            for index in range(1, int(items.Count) + 1):
                if scanned >= scan_limit or len(messages) >= limit:
                    break
                scanned += 1
                try:
                    item = items.Item(index)
                    if _safe_getattr(item, "Class", None) != OL_MAIL:
                        continue
                except Exception:
                    continue
                summary = self._message_summary(item, resolved_store_id)
                if needle and needle not in " ".join(
                    str(summary.get(key) or "")
                    for key in ("subject", "sender_name", "sender_address", "preview")
                ).casefold():
                    continue
                messages.append(summary)
            return {
                "provider": self.provider_id,
                "folder": self._folder_summary(target, resolved_store_id),
                "messages": messages,
                "scanned": scanned,
                "truncated": scanned >= scan_limit and len(messages) < limit,
            }

    def get_message(self, *, entry_id: str, store_id: str | None) -> dict[str, Any]:
        with self._session() as (_, namespace):
            item = self._get_item(namespace, entry_id, store_id)
            self._require_mail_item(item)
            return self._message_detail(item, store_id)

    def create_draft(
        self,
        *,
        kind: str,
        body: str,
        body_type: str,
        subject: str,
        to: list[str],
        cc: list[str],
        bcc: list[str],
        source_entry_id: str | None,
        source_store_id: str | None,
        attachments: list[str] | None = None,
    ) -> dict[str, Any]:
        with self._session() as (application, namespace):
            if kind == "new":
                draft = application.CreateItem(OL_MAIL_ITEM)
                draft.Subject = subject
            else:
                if not source_entry_id:
                    raise OutlookComError(f"source_entry_id is required for {kind}.")
                source = self._get_item(namespace, source_entry_id, source_store_id)
                self._require_mail_item(source)
                if kind == "reply":
                    draft = source.Reply()
                elif kind == "reply_all":
                    draft = source.ReplyAll()
                else:
                    draft = source.Forward()
                if subject:
                    draft.Subject = subject

            if to:
                draft.To = "; ".join(to)
            if cc:
                draft.CC = "; ".join(cc)
            if bcc:
                draft.BCC = "; ".join(bcc)
            self._set_body(draft, body, body_type, prepend=(kind != "new"))
            
            if attachments:
                from pathlib import Path

                for path_str in attachments:
                    resolved_path = Path(path_str).resolve()
                    from agent.corporate_path_access import request_path_access

                    policy_error = request_path_access(
                        resolved_path,
                        purpose="attach this local file to an Outlook draft",
                    )
                    if policy_error:
                        raise OutlookComError(policy_error)
                    if not resolved_path.exists():
                        raise OutlookComError(f"Attachment file not found: {path_str}")
                    draft.Attachments.Add(str(resolved_path))
                    
            draft.Save()
            return self._draft_summary(draft)

    def update_draft(
        self,
        *,
        entry_id: str,
        store_id: str | None,
        subject: str | None,
        body: str | None,
        body_type: str,
        to: list[str] | None,
        cc: list[str] | None,
        bcc: list[str] | None,
        attachments: list[str] | None = None,
    ) -> dict[str, Any]:
        with self._session() as (_, namespace):
            draft = self._get_item(namespace, entry_id, store_id)
            self._require_mail_item(draft)
            if bool(getattr(draft, "Sent", False)):
                raise OutlookComError("The selected message has already been sent.")
            if subject is not None:
                draft.Subject = subject
            if body is not None:
                self._set_body(draft, body, body_type, prepend=False)
            if to is not None:
                draft.To = "; ".join(to)
            if cc is not None:
                draft.CC = "; ".join(cc)
            if bcc is not None:
                draft.BCC = "; ".join(bcc)
                
            if attachments:
                from pathlib import Path

                for path_str in attachments:
                    resolved_path = Path(path_str).resolve()
                    from agent.corporate_path_access import request_path_access

                    policy_error = request_path_access(
                        resolved_path,
                        purpose="attach this local file to an Outlook draft",
                    )
                    if policy_error:
                        raise OutlookComError(policy_error)
                    if not resolved_path.exists():
                        raise OutlookComError(f"Attachment file not found: {path_str}")
                    draft.Attachments.Add(str(resolved_path))
                    
            draft.Save()
            return self._draft_summary(draft)

    @staticmethod
    def _get_item(namespace: Any, entry_id: str, store_id: str | None) -> Any:
        try:
            return namespace.GetItemFromID(entry_id, store_id) if store_id else namespace.GetItemFromID(entry_id)
        except Exception as exc:
            raise OutlookComError("The message could not be found in Outlook.") from exc

    @staticmethod
    def _get_folder(namespace: Any, entry_id: str, store_id: str | None) -> Any:
        try:
            return namespace.GetFolderFromID(entry_id, store_id) if store_id else namespace.GetFolderFromID(entry_id)
        except Exception as exc:
            raise OutlookComError("The folder could not be found in Outlook.") from exc

    def _resolve_folder(
        self,
        namespace: Any,
        *,
        store_id: str | None,
        folder_entry_id: str | None,
        folder: str,
    ) -> Any:
        if folder_entry_id:
            return self._get_folder(namespace, folder_entry_id, store_id)
        key = folder.replace("_", "").replace("-", "").casefold()
        folder_type = DEFAULT_FOLDERS.get(key)
        if folder_type is None:
            raise OutlookComError(
                "Unknown well-known folder. Use mail_list_folders and pass "
                "folder_entry_id for custom or corporate folders."
            )
        if store_id:
            store = namespace.GetStoreFromID(store_id)
            return store.GetDefaultFolder(folder_type)
        return namespace.GetDefaultFolder(folder_type)

    def _stores(self, namespace: Any) -> list[dict[str, Any]]:
        stores: list[dict[str, Any]] = []
        collection = namespace.Stores
        for index in range(1, int(collection.Count) + 1):
            store = collection.Item(index)
            root = store.GetRootFolder()
            stores.append(
                {
                    "name": getattr(store, "DisplayName", None),
                    "store_id": getattr(store, "StoreID", None),
                    "root_entry_id": getattr(root, "EntryID", None),
                    "is_data_file_store": bool(getattr(store, "IsDataFileStore", False)),
                    "exchange_store_type": getattr(store, "ExchangeStoreType", None),
                }
            )
        return stores

    def _folder_children(
        self,
        parent: Any,
        store_id: str,
        *,
        recursive: bool,
        depth: int = 0,
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        folders = parent.Folders
        for index in range(1, int(folders.Count) + 1):
            folder = folders.Item(index)
            summary = self._folder_summary(folder, store_id)
            summary["depth"] = depth
            result.append(summary)
            if recursive:
                result.extend(
                    self._folder_children(
                        folder,
                        store_id,
                        recursive=True,
                        depth=depth + 1,
                    )
                )
        return result

    @staticmethod
    def _folder_store_id(folder: Any) -> str | None:
        try:
            return folder.StoreID
        except Exception:
            try:
                return folder.Store.StoreID
            except Exception:
                return None

    @staticmethod
    def _folder_summary(folder: Any, store_id: str | None) -> dict[str, Any]:
        return {
            "name": getattr(folder, "Name", None),
            "folder_path": getattr(folder, "FolderPath", None),
            "entry_id": getattr(folder, "EntryID", None),
            "store_id": store_id,
            "item_count": getattr(folder, "Items", None).Count if getattr(folder, "Items", None) is not None else None,
            "unread_count": getattr(folder, "UnReadItemCount", None),
        }

    def _message_summary(self, item: Any, store_id: str | None) -> dict[str, Any]:
        body = str(_safe_getattr(item, "Body", "") or "")
        attachments = _safe_getattr(item, "Attachments", None)
        attachments_count = _safe_getattr(attachments, "Count", 0) if attachments is not None else 0
        return {
            "entry_id": _safe_getattr(item, "EntryID", None),
            "store_id": store_id,
            "subject": _safe_getattr(item, "Subject", None),
            "sender_name": _safe_getattr(item, "SenderName", None),
            "sender_address": self._sender_address(item),
            "received_at": _iso_datetime(_safe_getattr(item, "ReceivedTime", None)),
            "sent_at": _iso_datetime(_safe_getattr(item, "SentOn", None)),
            "unread": bool(_safe_getattr(item, "UnRead", False)),
            "importance": _safe_getattr(item, "Importance", None),
            "has_attachments": int(attachments_count) > 0,
            "preview": _message_preview(body),
        }

    def _message_detail(self, item: Any, store_id: str | None) -> dict[str, Any]:
        attachments = _safe_getattr(item, "Attachments", None)
        attachments_count = _safe_getattr(attachments, "Count", 0) if attachments is not None else 0
        attachments_list = []
        if attachments is not None:
            for index in range(1, int(attachments_count) + 1):
                try:
                    att_item = attachments.Item(index)
                    attachments_list.append({
                        "name": _safe_getattr(att_item, "FileName", None),
                        "size": _safe_getattr(att_item, "Size", None),
                    })
                except Exception:
                    pass
        return {
            **self._message_summary(item, store_id),
            "to": _safe_getattr(item, "To", None),
            "cc": _safe_getattr(item, "CC", None),
            "bcc": _safe_getattr(item, "BCC", None),
            "body": _safe_getattr(item, "Body", None),
            "html_body": _safe_getattr(item, "HTMLBody", None),
            "conversation_topic": _safe_getattr(item, "ConversationTopic", None),
            "categories": _safe_getattr(item, "Categories", None),
            "attachments": attachments_list,
        }

    def _draft_summary(self, draft: Any) -> dict[str, Any]:
        parent = _safe_getattr(draft, "Parent", None)
        attachments_list = []
        try:
            attachments = _safe_getattr(draft, "Attachments", None)
            if attachments is not None:
                attachments_count = _safe_getattr(attachments, "Count", 0)
                for i in range(1, int(attachments_count) + 1):
                    try:
                        att_item = attachments.Item(i)
                        attachments_list.append(_safe_getattr(att_item, "FileName", None))
                    except Exception:
                        pass
        except Exception:
            pass
        return {
            "success": True,
            "entry_id": _safe_getattr(draft, "EntryID", None),
            "store_id": self._folder_store_id(parent) if parent is not None else None,
            "subject": _safe_getattr(draft, "Subject", None),
            "to": _safe_getattr(draft, "To", None),
            "cc": _safe_getattr(draft, "CC", None),
            "bcc": _safe_getattr(draft, "BCC", None),
            "attachments": attachments_list,
            "saved": True,
            "sent": bool(_safe_getattr(draft, "Sent", False)),
        }

    @staticmethod
    def _set_body(draft: Any, body: str, body_type: str, *, prepend: bool) -> None:
        if body_type.casefold() == "html":
            content = body
            if prepend:
                existing = str(getattr(draft, "HTMLBody", "") or "")
                content = f"{body}<br><br>{existing}"
            draft.HTMLBody = content
            return
        content = body
        if prepend:
            existing = str(getattr(draft, "Body", "") or "")
            content = f"{body}\r\n\r\n{existing}"
        draft.Body = content

    @staticmethod
    def _require_mail_item(item: Any) -> None:
        if getattr(item, "Class", None) != OL_MAIL:
            raise OutlookComError("The selected Outlook item is not an email message.")

    @staticmethod
    def _sender_address(item: Any) -> str | None:
        raw = _safe_getattr(item, "SenderEmailAddress", None)
        if str(_safe_getattr(item, "SenderEmailType", "") or "").upper() != "EX":
            return raw
        sender = _safe_getattr(item, "Sender", None)
        if sender is None:
            return raw
        try:
            exchange_user = sender.GetExchangeUser()
            primary = _safe_getattr(exchange_user, "PrimarySmtpAddress", None)
            if primary:
                return primary
        except Exception:
            pass
        try:
            return sender.PropertyAccessor.GetProperty(PR_SMTP_ADDRESS) or raw
        except Exception:
            return raw


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OutlookComError("received_after must be a valid ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _iso_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.astimezone()
        return value.isoformat()
    try:
        return str(value)
    except Exception:
        return None


def _message_preview(body: str, *, limit: int = 500) -> str:
    cleaned = _INVISIBLE_PREVIEW_CHARS_RE.sub(" ", body)
    cleaned = _PREVIEW_URL_RE.sub("[link]", cleaned)
    return " ".join(cleaned.split())[:limit]
