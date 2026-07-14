"""Select the configured desktop-mail provider."""

from __future__ import annotations

from collections.abc import Callable

from hermes_cli.config import cfg_get, read_raw_config
from plugins.outlook.providers.base import DesktopMailProvider
from plugins.outlook.providers.outlook_com import OutlookComProvider


ProviderFactory = Callable[[], DesktopMailProvider]

_PROVIDERS: dict[str, ProviderFactory] = {
    "outlook_com": OutlookComProvider,
}


def register_provider(
    provider_id: str,
    factory: ProviderFactory,
    *,
    override: bool = False,
) -> None:
    """Register a desktop-mail provider factory.

    Corporate client integrations can call this from plugin registration.
    Duplicate IDs fail closed unless the registering integration explicitly
    opts into replacement.
    """
    normalized = provider_id.strip().casefold()
    if not normalized:
        raise ValueError("provider_id is required")
    if normalized in _PROVIDERS and not override:
        raise ValueError(f"Desktop mail provider already registered: {provider_id}")
    _PROVIDERS[normalized] = factory


def configured_provider_id() -> str:
    config = read_raw_config()
    return str(
        cfg_get(config, "desktop_mail", "provider", default="outlook_com")
        or "outlook_com"
    ).strip().casefold()


def get_provider(provider_id: str | None = None) -> DesktopMailProvider:
    """Return a fresh provider instance.

    COM objects are intentionally not cached across tool calls or threads.
    Future corporate desktop clients register here while preserving the
    model-facing mail tool contract.
    """
    normalized = (provider_id or configured_provider_id()).strip().casefold()
    factory = _PROVIDERS.get(normalized)
    if factory is None:
        raise RuntimeError(f"Unknown desktop mail provider: {normalized}")
    return factory()
