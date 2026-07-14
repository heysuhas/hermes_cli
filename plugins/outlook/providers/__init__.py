"""Desktop mail provider interfaces and implementations."""

from plugins.outlook.providers.base import DesktopMailProvider
from plugins.outlook.providers.outlook_com import OutlookComProvider

__all__ = ["DesktopMailProvider", "OutlookComProvider"]

