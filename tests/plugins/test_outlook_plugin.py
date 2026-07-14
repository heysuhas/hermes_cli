from __future__ import annotations

import contextlib
import json
from types import SimpleNamespace
from pathlib import Path

import pytest
import yaml

from plugins.outlook import tools
from plugins.outlook import provider as provider_registry
from plugins.outlook.providers.outlook_com import (
    OutlookComError,
    OutlookComProvider,
    _message_preview,
)


class FakeProvider:
    def status(self):
        return {"available": True, "provider": "fake"}

    def list_folders(self, **kwargs):
        return {"folders": [{"entry_id": "f1", "store_id": "s1"}], "args": kwargs}

    def list_messages(self, **kwargs):
        return {
            "messages": [{"entry_id": "m1", "store_id": "s1", "subject": "Hello"}],
            "args": kwargs,
        }

    def get_message(self, **kwargs):
        return {"body": "Full message", **kwargs}

    def create_draft(self, **kwargs):
        return {"success": True, "entry_id": "d1", "sent": False, **kwargs}

    def update_draft(self, **kwargs):
        return {"success": True, "sent": False, **kwargs}


@pytest.fixture(autouse=True)
def fake_provider(monkeypatch):
    monkeypatch.setattr(tools, "get_provider", lambda: FakeProvider())


def test_list_messages_returns_provider_native_locators():
    result = json.loads(
        tools.handle_mail_list_messages(
            {"folder": "inbox", "limit": 5, "unread_only": True}
        )
    )
    assert result["messages"][0]["entry_id"] == "m1"
    assert result["messages"][0]["store_id"] == "s1"
    assert result["args"]["unread_only"] is True


def test_folder_discovery_is_not_hardcoded_to_default_mailbox():
    result = json.loads(
        tools.handle_mail_list_folders(
            {"store_id": "corporate-store", "recursive": True}
        )
    )
    assert result["args"] == {
        "store_id": "corporate-store",
        "parent_entry_id": None,
        "recursive": True,
    }


def test_create_new_draft_never_sends():
    result = json.loads(
        tools.handle_mail_create_draft(
            {
                "kind": "new",
                "to": ["alice@example.com"],
                "subject": "Draft",
                "body": "Review this first.",
            }
        )
    )
    assert result["success"] is True
    assert result["sent"] is False


def test_create_reply_requires_source_message():
    result = json.loads(
        tools.handle_mail_create_draft({"kind": "reply", "body": "Thanks"})
    )
    assert "source_entry_id is required" in result["error"]


def test_forward_requires_recipient():
    result = json.loads(
        tools.handle_mail_create_draft(
            {"kind": "forward", "source_entry_id": "m1", "body": "FYI"}
        )
    )
    assert "recipient" in result["error"]


def test_update_requires_a_change():
    result = json.loads(tools.handle_mail_update_draft({"entry_id": "d1"}))
    assert "at least one draft field" in result["error"]


def test_provider_errors_are_returned_to_model(monkeypatch):
    class BrokenProvider:
        def status(self):
            raise OutlookComError("classic Outlook is unavailable")

    monkeypatch.setattr(tools, "get_provider", lambda: BrokenProvider())
    result = json.loads(tools.handle_mail_status({}))
    assert result["error"] == "classic Outlook is unavailable"


def test_transient_com_failure_is_retried(monkeypatch):
    calls = {"count": 0}

    class FlakyProvider:
        def list_messages(self, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise Exception(
                    -2147352567,
                    "Exception occurred.",
                    (
                        4096,
                        "Microsoft Outlook",
                        "Sorry, something went wrong. You may want to try again.",
                        None,
                        0,
                        -2147352567,
                    ),
                )
            return {"messages": [], "args": kwargs}

    monkeypatch.setattr(tools, "get_provider", lambda: FlakyProvider())
    monkeypatch.setattr(tools.time, "sleep", lambda _: None)

    result = json.loads(tools.handle_mail_list_messages({"folder": "inbox"}))

    assert result["messages"] == []
    assert calls["count"] == 2


def test_unexpected_com_failure_includes_operation_and_hresult(monkeypatch):
    class BrokenProvider:
        def list_messages(self, **kwargs):
            raise Exception(
                -2147352567,
                "Exception occurred.",
                (
                    4096,
                    "Microsoft Outlook",
                    "Sorry, something went wrong. You may want to try again.",
                    None,
                    0,
                    -2147352567,
                ),
            )

    monkeypatch.setattr(tools, "get_provider", lambda: BrokenProvider())
    monkeypatch.setattr(tools.time, "sleep", lambda _: None)

    result = json.loads(tools.handle_mail_list_messages({"folder": "inbox"}))

    assert "list_messages" in result["error"]
    assert "hresult=-2147352567" in result["error"]
    assert "Sorry, something went wrong" in result["error"]


def test_plugin_registers_generic_non_sending_tools():
    import plugins.outlook as plugin

    registered = []
    ctx = SimpleNamespace(
        register_tool=lambda **kwargs: registered.append(kwargs),
        register_cli_command=lambda **kwargs: None,
    )
    plugin.register(ctx)
    assert {item["name"] for item in registered} == {
        "mail_client_status",
        "mail_list_folders",
        "mail_list_messages",
        "mail_get_message",
        "mail_create_draft",
        "mail_update_draft",
    }
    assert {item["toolset"] for item in registered} == {"desktop_mail"}
    assert all("send" not in item["name"] for item in registered)


def test_manifest_uses_bundled_backend_lifecycle():
    """The local service adapter must load before toolset resolution.

    Bundled standalone plugins require an independent plugins.enabled opt-in,
    which prevents their toolsets from appearing in `hermes tools` at all.
    Backend lifecycle plus check_fn gives the intended service gate: imported
    at startup, exposed only when classic Outlook is locally available.
    """
    manifest = yaml.safe_load(
        (Path(__file__).parents[2] / "plugins" / "outlook" / "plugin.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["kind"] == "backend"


def test_com_rejects_non_mail_item():
    with pytest.raises(OutlookComError, match="not an email message"):
        OutlookComProvider._require_mail_item(SimpleNamespace(Class=99))


def test_com_default_folder_mapping_is_adapter_internal():
    provider = OutlookComProvider()
    namespace = SimpleNamespace(
        GetDefaultFolder=lambda folder_type: ("default", folder_type)
    )
    assert provider._resolve_folder(
        namespace,
        store_id=None,
        folder_entry_id=None,
        folder="inbox",
    ) == ("default", 6)


def test_message_preview_removes_invisible_email_padding():
    assert _message_preview("Hello\u034f \u200c \u200b world") == "Hello world"


def test_message_preview_compacts_tracking_urls():
    assert _message_preview("Open <https://example.com/a/very/long/path> now") == "Open [link] now"


def test_provider_registry_supports_future_corporate_adapter(monkeypatch):
    class CorporateProvider(FakeProvider):
        provider_id = "corporate_client"

    monkeypatch.setitem(
        provider_registry._PROVIDERS,
        "corporate_client",
        CorporateProvider,
    )
    selected = provider_registry.get_provider("corporate_client")
    assert isinstance(selected, CorporateProvider)


def test_outlook_com_new_draft_saves_without_send():
    class Draft:
        Subject = ""
        To = ""
        CC = ""
        BCC = ""
        Body = ""
        Sent = False
        EntryID = "draft-entry"
        Parent = SimpleNamespace(StoreID="store-1")

        def __init__(self):
            self.saved = 0

        def Save(self):
            self.saved += 1

    draft = Draft()
    application = SimpleNamespace(CreateItem=lambda item_type: draft)

    class TestProvider(OutlookComProvider):
        @contextlib.contextmanager
        def _session(self):
            yield application, SimpleNamespace()

    result = TestProvider().create_draft(
        kind="new",
        body="Please review.",
        body_type="Text",
        subject="Test draft",
        to=["alice@example.com"],
        cc=[],
        bcc=[],
        source_entry_id=None,
        source_store_id=None,
    )
    assert draft.saved == 1
    assert result["sent"] is False
    assert result["entry_id"] == "draft-entry"
    assert not hasattr(draft, "Send")


def test_outlook_com_draft_with_attachments(monkeypatch):
    class MockAttachmentItem:
        def __init__(self, filename):
            self.FileName = filename

    class MockAttachments:
        def __init__(self):
            self.items = []
            self.Count = 0

        def Add(self, path):
            self.items.append(path)
            self.Count = len(self.items)

        def Item(self, index):
            import os
            return MockAttachmentItem(os.path.basename(self.items[index - 1]))

    class Draft:
        Subject = ""
        To = ""
        CC = ""
        BCC = ""
        Body = ""
        Sent = False
        EntryID = "draft-entry"
        Parent = SimpleNamespace(StoreID="store-1")

        def __init__(self):
            self.saved = 0
            self.Attachments = MockAttachments()

        def Save(self):
            self.saved += 1

    draft = Draft()
    application = SimpleNamespace(CreateItem=lambda item_type: draft)

    class TestProvider(OutlookComProvider):
        @contextlib.contextmanager
        def _session(self):
            yield application, SimpleNamespace()

    from pathlib import Path
    monkeypatch.setattr(Path, "exists", lambda self: True)

    result = TestProvider().create_draft(
        kind="new",
        body="Please review.",
        body_type="Text",
        subject="Test draft",
        to=["alice@example.com"],
        cc=[],
        bcc=[],
        source_entry_id=None,
        source_store_id=None,
        attachments=["C:\\path\\to\\test_doc.pdf"]
    )
    assert draft.saved == 1
    assert result["sent"] is False
    assert result["entry_id"] == "draft-entry"
    assert result["attachments"] == ["test_doc.pdf"]
    assert len(draft.Attachments.items) == 1
    assert "test_doc.pdf" in draft.Attachments.items[0]
