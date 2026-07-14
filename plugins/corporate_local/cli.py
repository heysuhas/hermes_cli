"""Operator CLI for corporate-local mode."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from agent.corporate_policy import get_corporate_policy


RULE_PREFIX = "Hermes Corporate Local"


def register_cli(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="corporate_command")
    sub.add_parser("status", help="Show effective policy and firewall status")
    firewall = sub.add_parser("firewall", help="Manage Windows outbound rules")
    firewall_sub = firewall.add_subparsers(dest="firewall_command")
    firewall_sub.add_parser("status", help="List installed Hermes rules")
    firewall_sub.add_parser("install", help="Install outbound-deny rules (administrator)")
    firewall_sub.add_parser("remove", help="Remove Hermes outbound rules (administrator)")
    roots = sub.add_parser("roots", help="Manage user-approved working folders")
    roots_sub = roots.add_subparsers(dest="roots_command")
    roots_sub.add_parser("list", help="List effective approved roots")
    add_root = roots_sub.add_parser("add", help="Add an approved working folder")
    add_root.add_argument("path")
    remove_root = roots_sub.add_parser("remove", help="Remove an approved working folder")
    remove_root.add_argument("path")
    parser.set_defaults(func=corporate_command)


def _powershell() -> str:
    return shutil.which("pwsh") or shutil.which("powershell") or "powershell"


def _run(script: str) -> tuple[int, str]:
    completed = subprocess.run(
        [_powershell(), "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=60,
    )
    output = (completed.stdout or completed.stderr or "").strip()
    return completed.returncode, output


def _candidate_executables() -> list[str]:
    candidates = {
        str(Path(sys.executable).resolve()),
    }
    for command in ("python", "python3", "node", "cmd", "powershell", "pwsh"):
        value = shutil.which(command)
        if value:
            candidates.add(str(Path(value).resolve()))
    windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
    for path in (
        windows / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe",
        windows / "System32" / "cmd.exe",
    ):
        if path.exists():
            candidates.add(str(path.resolve()))
    for root in (
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    ):
        office_root = root / "Microsoft Office"
        if not office_root.exists():
            continue
        for executable_name in (
            "OUTLOOK.EXE",
            "WINWORD.EXE",
            "EXCEL.EXE",
            "POWERPNT.EXE",
        ):
            for path in office_root.rglob(executable_name):
                candidates.add(str(path.resolve()))
    broker = get_corporate_policy().broker_executable_path
    if broker:
        candidates.discard(str(broker.resolve(strict=False)))
    return sorted(candidates)


def _broker_identity_status() -> tuple[bool, str]:
    policy = get_corporate_policy()
    executable = policy.broker_executable_path
    if executable is None:
        return True, "not configured (loopback-only broker expected)"
    escaped = str(executable).replace("'", "''")
    code, output = _run(
        f"$sig = Get-AuthenticodeSignature -LiteralPath '{escaped}'; "
        "[pscustomobject]@{Status=[string]$sig.Status; "
        "Thumbprint=[string]$sig.SignerCertificate.Thumbprint} | "
        "ConvertTo-Json -Compress"
    )
    if code:
        return False, output or "unable to inspect broker signature"
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return False, output or "invalid broker signature response"
    thumbprint = str(payload.get("Thumbprint") or "").replace(" ", "").upper()
    valid = str(payload.get("Status") or "").casefold() == "valid"
    if policy.broker_signer_thumbprint:
        valid = valid and thumbprint == policy.broker_signer_thumbprint
    return valid, output


def _install_firewall() -> tuple[int, str]:
    broker_valid, broker_status = _broker_identity_status()
    if not broker_valid:
        return 1, f"Broker executable signature validation failed: {broker_status}"
    commands: list[str] = [
        f"Get-NetFirewallRule -DisplayName '{RULE_PREFIX}*' "
        "-ErrorAction SilentlyContinue | Remove-NetFirewallRule"
    ]
    for executable in _candidate_executables():
        escaped = executable.replace("'", "''")
        identity = hashlib.sha256(
            executable.casefold().encode("utf-8")
        ).hexdigest()[:12]
        name = f"{RULE_PREFIX} Block {identity}"
        commands.append(
            f"Remove-NetFirewallRule -DisplayName '{name}' -ErrorAction SilentlyContinue; "
            f"New-NetFirewallRule -DisplayName '{name}' -Direction Outbound "
            f"-Action Block -Program '{escaped}' -RemoteAddress Internet "
            f"-Profile Any | Out-Null"
        )
    return _run("; ".join(commands) + "; 'installed'")


def _remove_firewall() -> tuple[int, str]:
    return _run(
        f"Get-NetFirewallRule -DisplayName '{RULE_PREFIX}*' "
        "-ErrorAction SilentlyContinue | Remove-NetFirewallRule; 'removed'"
    )


def _firewall_status() -> tuple[int, str]:
    return _run(
        f"Get-NetFirewallRule -DisplayName '{RULE_PREFIX}*' "
        "-ErrorAction SilentlyContinue | ForEach-Object { "
        "$app = $_ | Get-NetFirewallApplicationFilter; "
        "[pscustomobject]@{DisplayName=$_.DisplayName; Enabled=$_.Enabled; "
        "Direction=$_.Direction; Action=$_.Action; Program=$app.Program} "
        "} | ConvertTo-Json"
    )


def corporate_command(args: argparse.Namespace) -> int:
    command = getattr(args, "corporate_command", None)
    firewall_command = getattr(args, "firewall_command", None)
    roots_command = getattr(args, "roots_command", None)
    policy = get_corporate_policy(refresh=True)
    from agent.corporate_path_access import effective_allowed_roots

    effective_roots = effective_allowed_roots(policy)
    if command == "status":
        code, firewall = _firewall_status() if os.name == "nt" else (0, "not-windows")
        broker_valid, broker_identity = (
            _broker_identity_status() if os.name == "nt" else (False, "not-windows")
        )
        print(
            json.dumps(
                {
                    "enabled": policy.enabled,
                    "source": policy.source,
                    "fingerprint": policy.fingerprint(),
                    "allowed_tools": sorted(policy.allowed_tools),
                    "allowed_plugins": sorted(policy.allowed_plugins),
                    "allowed_roots": [str(path) for path in effective_roots],
                    "administrator_root_parents": [
                        str(path) for path in policy.allowed_root_parents
                    ],
                    "path_access_hint": (
                        "Retry a blocked local operation and approve the inline "
                        "folder prompt, or run `hermes corporate roots add <folder>`."
                    ),
                    "broker_url": policy.broker_url,
                    "broker_identity_valid": broker_valid,
                    "broker_identity": broker_identity,
                    "allow_intranet": policy.allow_intranet,
                    "diagnostics": list(policy.diagnostics),
                    "firewall": firewall,
                },
                indent=2,
            )
        )
        return code
    if command == "firewall":
        if os.name != "nt":
            print("Corporate Firewall management is available only on Windows.")
            return 1
        if firewall_command == "install":
            code, output = _install_firewall()
        elif firewall_command == "remove":
            code, output = _remove_firewall()
        else:
            code, output = _firewall_status()
        print(output)
        if code:
            print("Run this command from an elevated administrator terminal.")
        return code
    if command == "roots":
        if roots_command in {None, "list"}:
            print(json.dumps([str(path) for path in effective_roots], indent=2))
            return 0
        target = Path(args.path).expanduser().resolve(strict=False)
        if not policy.allows_root_selection(target):
            print("Root is outside the administrator-approved parent directories.")
            return 1
        from hermes_cli.config import load_config, save_config

        config = load_config()
        product = config.setdefault("product", {})
        roots = [
            str(Path(value).expanduser().resolve(strict=False))
            for value in product.get("allowed_roots", [])
        ]
        if roots_command == "add" and str(target) not in roots:
            roots.append(str(target))
        elif roots_command == "remove":
            roots = [value for value in roots if value != str(target)]
        product["allowed_roots"] = roots
        save_config(config)
        from agent.corporate_policy import reset_policy_cache

        reset_policy_cache()
        print(json.dumps(roots, indent=2))
        return 0
    print(
        "usage: hermes corporate "
        "{status,firewall {status,install,remove},roots {list,add,remove}}"
    )
    return 2
