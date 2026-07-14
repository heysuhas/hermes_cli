"""Provider-neutral contract for locally installed desktop mail clients."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class DesktopMailProvider(ABC):
    """Contract implemented by each desktop mail application adapter.

    Tool handlers depend only on this interface. A future corporate mail
    client can be integrated without changing model-facing schemas or agent
    orchestration.
    """

    provider_id: str

    @abstractmethod
    def status(self) -> dict[str, Any]:
        """Return application and session health without exposing secrets."""

    @abstractmethod
    def list_folders(
        self,
        *,
        store_id: str | None = None,
        parent_entry_id: str | None = None,
        recursive: bool = False,
    ) -> dict[str, Any]:
        """List mailbox stores or folders and return provider-native locators."""

    @abstractmethod
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
        """List message summaries and opaque IDs for subsequent operations."""

    @abstractmethod
    def get_message(self, *, entry_id: str, store_id: str | None) -> dict[str, Any]:
        """Read one message by its provider-native locator."""

    @abstractmethod
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
        """Create and save a draft without sending it."""

    @abstractmethod
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
        """Update and save an existing unsent draft."""

