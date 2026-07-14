"""Operator diagnostics for the desktop-mail integration."""

from __future__ import annotations

import argparse
import json

from plugins.outlook.provider import get_provider


def register_cli(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="mail_command")
    sub.add_parser("status", help="Connect to classic Outlook and inspect the active profile")
    sub.add_parser("folders", help="List configured Outlook mailbox stores")
    parser.set_defaults(func=outlook_command)


def outlook_command(args: argparse.Namespace) -> int:
    command = getattr(args, "mail_command", None)
    try:
        provider = get_provider()
        if command == "status":
            print(json.dumps(provider.status(), indent=2, default=str))
            return 0
        if command == "folders":
            print(json.dumps(provider.list_folders(), indent=2, default=str))
            return 0
    except Exception as exc:
        print(f"Desktop mail error: {exc}")
        return 1
    print("usage: hermes outlook {status,folders}")
    return 2

