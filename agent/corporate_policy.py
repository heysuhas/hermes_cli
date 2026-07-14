"""Corporate-local product policy and enforcement helpers.

The policy is intentionally small and dependency-light so it can be imported
from tool discovery, plugin loading, prompt assembly, terminal execution, and
skill installation without creating circular imports.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

import yaml


CORPORATE_MODE = "corporate_local"
POLICY_VERSION = 1

DEFAULT_ALLOWED_TOOLS = frozenset(
    {
        "terminal",
        "process",
        "read_file",
        "write_file",
        "patch",
        "search_files",
        "skills_list",
        "skill_view",
        "skill_manage",
        "todo",
        "memory",
        "session_search",
        "clarify",
        "local_access_status",
        "mail_client_status",
        "mail_list_folders",
        "mail_list_messages",
        "mail_get_message",
        "mail_create_draft",
        "mail_update_draft",
        "document_inspect",
        "document_extract",
        "office_plan_changes",
        "office_apply_changes",
    }
)

DEFAULT_ALLOWED_PLUGINS = frozenset({"outlook", "corporate_office", "corporate_local"})

_NETWORK_COMMAND_RE = re.compile(
    r"(?ix)"
    r"(?:https?|ftp|ssh|git|ws|wss)://|"
    r"\b(?:curl|wget|Invoke-WebRequest|Invoke-RestMethod|Start-BitsTransfer|"
    r"bitsadmin|certutil\s+-urlcache|ssh|scp|sftp|ftp|telnet|nc|ncat|"
    r"Test-NetConnection|nslookup|Resolve-DnsName|ping|tracert|"
    r"npm\s+(?:install|view|info|search)|"
    r"git\s+(?:clone|fetch|pull|push|ls-remote)|"
    r"hermes\s+update|"
    r"winget\s+(?:install|upgrade)|choco\s+install|scoop\s+install)\b"
)

_PACKAGE_INSTALL_RE = re.compile(
    r"(?i)\b(?:pip(?:3)?\s+install|python(?:3)?\s+-m\s+pip\s+install|"
    r"uv\s+(?:pip\s+)?install)\b"
)

_CORPORATE_AUTHORIZATION_COMMAND_RE = re.compile(
    r"(?i)(?:^|[;&|]\s*)"
    r"(?:hermes(?:\.exe)?\s+)?corporate\s+roots\s+"
    r"(?:add|remove|clear|reset)\b"
)

_WINDOWS_PATH_RE = re.compile(
    r'(?i)(?:"([^"]*(?:[A-Z]:\\|\\\\)[^"]*)"|'
    r"'([^']*(?:[A-Z]:\\|\\\\)[^']*)'|"
    r"((?:[A-Z]:\\|\\\\)[^\s|;&<>]+))"
)


def _program_data_policy_path() -> Path:
    program_data = os.environ.get("PROGRAMDATA")
    if program_data:
        return Path(program_data) / "Hermes" / "policy.yaml"
    return Path(r"C:\ProgramData\Hermes\policy.yaml")


def _load_user_config() -> dict[str, Any]:
    try:
        from hermes_cli.config import load_config

        config = load_config()
        return config if isinstance(config, dict) else {}
    except Exception:
        return {}


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        return {}
    return value if isinstance(value, dict) else {}


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def _canonical_path(value: str | os.PathLike[str]) -> Path:
    return Path(value).expanduser().resolve(strict=False)


@dataclass(frozen=True)
class CorporatePolicy:
    enabled: bool = False
    source: str = "disabled"
    version: int = POLICY_VERSION
    allowed_tools: frozenset[str] = DEFAULT_ALLOWED_TOOLS
    allowed_plugins: frozenset[str] = DEFAULT_ALLOWED_PLUGINS
    allowed_roots: tuple[Path, ...] = ()
    allowed_root_parents: tuple[Path, ...] = ()
    broker_url: str = "http://127.0.0.1:8765"
    broker_token_file: Path | None = None
    broker_public_key_file: Path | None = None
    broker_executable_path: Path | None = None
    broker_signer_thumbprint: str = ""
    allowed_network_hosts: frozenset[str] = frozenset(
        {"localhost", "127.0.0.1", "::1"}
    )
    allow_intranet: bool = False
    audit_enabled: bool = True
    audit_paths: bool = True
    audit_retention_days: int = 30
    max_document_bytes: int = 50 * 1024 * 1024
    terminal_block_network: bool = True
    terminal_allowed_commands: tuple[str, ...] = ()
    terminal_denied_patterns: tuple[str, ...] = ()
    skill_allow_local_creation: bool = True
    skill_require_broker_signature: bool = True
    diagnostics: tuple[str, ...] = field(default_factory=tuple)

    def allows_tool(self, tool_name: str) -> bool:
        return not self.enabled or tool_name in self.allowed_tools

    def allows_plugin(self, key: str, name: str = "") -> bool:
        if not self.enabled:
            return True
        candidates = {key, name, key.rsplit("/", 1)[-1]}
        return bool(candidates & self.allowed_plugins)

    def allows_path(self, value: str | os.PathLike[str]) -> bool:
        if not self.enabled or not self.allowed_roots:
            return True
        try:
            target = _canonical_path(value)
        except (OSError, ValueError):
            return False
        return any(target == root or target.is_relative_to(root) for root in self.allowed_roots)

    def allows_root_selection(self, value: str | os.PathLike[str]) -> bool:
        try:
            target = _canonical_path(value)
        except (OSError, ValueError):
            return False
        if not self.allowed_root_parents:
            return True
        return any(
            target == parent or target.is_relative_to(parent)
            for parent in self.allowed_root_parents
        )

    def path_error(self, value: str | os.PathLike[str]) -> str | None:
        if self.allows_path(value):
            return None
        return (
            "Corporate policy blocked this path because it is outside the "
            "administrator/user-approved working roots."
        )

    def allows_url(self, url: str) -> bool:
        if not self.enabled:
            return True
        try:
            parsed = urlparse(url)
            if parsed.scheme.lower() not in {"http", "https"}:
                return False
            hostname = (parsed.hostname or "").strip().lower()
        except ValueError:
            return False
        if not hostname:
            return False
        if hostname in {"localhost", "127.0.0.1", "::1"}:
            return True
        try:
            address = ipaddress.ip_address(hostname)
            if address.is_loopback:
                return True
            if self.allow_intranet and (
                address.is_private or address.is_link_local
            ):
                return True
        except ValueError:
            pass
        if self.allow_intranet and hostname in self.allowed_network_hosts:
            try:
                addresses = {
                    info[4][0]
                    for info in socket.getaddrinfo(hostname, None)
                    if info and info[4]
                }
            except OSError:
                addresses = set()
            if addresses and all(
                ipaddress.ip_address(address).is_private
                or ipaddress.ip_address(address).is_loopback
                or ipaddress.ip_address(address).is_link_local
                for address in addresses
            ):
                return True
        return False

    def terminal_command_error(self, command: str) -> str | None:
        if not self.enabled:
            return None
        if _CORPORATE_AUTHORIZATION_COMMAND_RE.search(command or ""):
            return (
                "Corporate policy blocked this authorization command. Only the "
                "user may change approved roots through the Hermes approval UI "
                "or a separate user-controlled shell; the agent cannot grant "
                "itself filesystem access."
            )
        for pattern in self.terminal_denied_patterns:
            try:
                if re.search(pattern, command, flags=re.IGNORECASE):
                    return (
                        "Corporate policy blocked this command because it matches "
                        "an administrator-denied command pattern."
                    )
            except re.error:
                continue
        if not self.terminal_block_network:
            return None
        if _PACKAGE_INSTALL_RE.search(command or "") and not re.search(
            r"(?i)(?:^|\s)--no-index(?:\s|$)", command
        ):
            return (
                "Corporate policy blocked this package installation because it "
                "could contact a public package index. Use an approved local "
                "artifact with --no-index or request broker-mediated packaging."
            )
        if any(
            re.search(pattern, command, flags=re.IGNORECASE)
            for pattern in self.terminal_allowed_commands
        ):
            return None
        if _NETWORK_COMMAND_RE.search(command or ""):
            return (
                "Corporate policy blocked this command because it can access "
                "the network. Use local files/tools or the approved skill broker."
            )
        return None

    def terminal_approval_reason(self, command: str) -> str | None:
        if self.enabled and _PACKAGE_INSTALL_RE.search(command or ""):
            return "install packages from an approved local artifact"
        return None

    def terminal_referenced_path_error(self, command: str) -> str | None:
        if not self.enabled or not self.allowed_roots:
            return None
        for match in _WINDOWS_PATH_RE.finditer(command or ""):
            value = next(
                (group for group in match.groups() if group),
                "",
            )
            # Quoted matches may include prose before the path; start at the
            # drive/UNC marker and retain the full path thereafter.
            drive = re.search(r"(?i)([A-Z]:\\|\\\\)", value)
            if drive:
                value = value[drive.start():]
            if value and not self.allows_path(value):
                return (
                    "Corporate policy blocked this command because it references "
                    "a path outside the approved working roots. Add/select that "
                    "root explicitly before using the terminal."
                )
        return None

    def fingerprint(self) -> str:
        payload = {
            "version": self.version,
            "allowed_tools": sorted(self.allowed_tools),
            "allowed_plugins": sorted(self.allowed_plugins),
            "allowed_roots": [str(path) for path in self.allowed_roots],
            "allowed_root_parents": [
                str(path) for path in self.allowed_root_parents
            ],
            "broker_url": self.broker_url,
            "allowed_network_hosts": sorted(self.allowed_network_hosts),
            "allow_intranet": self.allow_intranet,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]


_policy_lock = threading.Lock()
_policy_cache: CorporatePolicy | None = None


def _build_policy() -> CorporatePolicy:
    config = _load_user_config()
    product = config.get("product") if isinstance(config.get("product"), dict) else {}
    selected_mode = os.environ.get("HERMES_PRODUCT_MODE") or product.get("mode") or ""
    enabled = str(selected_mode).strip().lower() == CORPORATE_MODE
    if not enabled:
        return CorporatePolicy()

    policy_path = _program_data_policy_path()
    admin = _read_yaml(policy_path)
    corporate = admin.get("corporate") if isinstance(admin.get("corporate"), dict) else admin
    if not isinstance(corporate, dict):
        corporate = {}

    diagnostics: list[str] = []
    source = str(policy_path) if policy_path.exists() else "safe defaults"
    if not policy_path.exists():
        diagnostics.append(f"Administrator policy not found at {policy_path}; safe defaults applied.")

    tools = _string_set(corporate.get("allowed_tools"))
    plugins = _string_set(corporate.get("allowed_plugins"))
    user_tools = _string_set(product.get("allowed_tools"))
    user_plugins = _string_set(product.get("allowed_plugins"))
    effective_tools = tools or set(DEFAULT_ALLOWED_TOOLS)
    effective_plugins = plugins or set(DEFAULT_ALLOWED_PLUGINS)
    if user_tools:
        effective_tools &= user_tools
    if user_plugins:
        effective_plugins &= user_plugins
    fixed_roots = corporate.get("allowed_roots", [])
    if not isinstance(fixed_roots, list):
        fixed_roots = []
    parent_roots = corporate.get("allowed_root_parents", [])
    if not isinstance(parent_roots, list):
        parent_roots = []
    selected_roots = product.get("allowed_roots", [])
    if not isinstance(selected_roots, list):
        selected_roots = []
    canonical_parents: list[Path] = []
    for raw_parent in parent_roots:
        try:
            canonical_parents.append(_canonical_path(str(raw_parent)))
        except (OSError, ValueError):
            diagnostics.append(f"Ignored invalid allowed root parent: {raw_parent!r}")
    canonical_roots: list[Path] = []
    for raw_root in [*fixed_roots, *selected_roots]:
        try:
            candidate = _canonical_path(str(raw_root))
            if canonical_parents and not any(
                candidate == parent or candidate.is_relative_to(parent)
                for parent in canonical_parents
            ):
                diagnostics.append(
                    f"Ignored root outside administrator parents: {candidate}"
                )
                continue
            canonical_roots.append(candidate)
        except (OSError, ValueError):
            diagnostics.append(f"Ignored invalid approved root: {raw_root!r}")
    if not canonical_roots:
        terminal_cwd = os.environ.get("TERMINAL_CWD")
        try:
            canonical_roots.append(
                _canonical_path(terminal_cwd) if terminal_cwd else Path.cwd().resolve()
            )
        except (OSError, ValueError):
            pass

    # Always allow HERMES_HOME so the agent can access its own skills/configs/caches
    from hermes_constants import get_hermes_home
    try:
        canonical_roots.append(_canonical_path(get_hermes_home()))
    except Exception:
        pass

    # Always allow user profile folders for output and drafting
    for path_name in ("Documents", "Downloads", "Desktop"):
        try:
            canonical_roots.append(_canonical_path(Path.home() / path_name))
        except Exception:
            pass

    network = corporate.get("network") if isinstance(corporate.get("network"), dict) else {}
    broker = corporate.get("broker") if isinstance(corporate.get("broker"), dict) else {}
    audit = corporate.get("audit") if isinstance(corporate.get("audit"), dict) else {}
    terminal = corporate.get("terminal") if isinstance(corporate.get("terminal"), dict) else {}
    skills = corporate.get("skills") if isinstance(corporate.get("skills"), dict) else {}

    broker_url = str(
        broker.get("url")
        or product.get("broker_url")
        or "http://127.0.0.1:8765"
    ).rstrip("/")
    allowed_hosts = {"localhost", "127.0.0.1", "::1"}
    allowed_hosts.update(host.lower() for host in _string_set(network.get("allowed_hosts")))

    return CorporatePolicy(
        enabled=True,
        source=source,
        version=int(corporate.get("version") or POLICY_VERSION),
        allowed_tools=frozenset(effective_tools),
        allowed_plugins=frozenset(effective_plugins),
        allowed_roots=tuple(dict.fromkeys(canonical_roots)),
        allowed_root_parents=tuple(dict.fromkeys(canonical_parents)),
        broker_url=broker_url,
        broker_token_file=(
            _canonical_path(str(broker["token_file"]))
            if broker.get("token_file")
            else None
        ),
        broker_public_key_file=(
            _canonical_path(str(broker["public_key_file"]))
            if broker.get("public_key_file")
            else None
        ),
        broker_executable_path=(
            _canonical_path(str(broker["executable_path"]))
            if broker.get("executable_path")
            else None
        ),
        broker_signer_thumbprint=str(
            broker.get("signer_thumbprint") or ""
        ).replace(" ", "").upper(),
        allowed_network_hosts=frozenset(allowed_hosts),
        allow_intranet=bool(network.get("allow_intranet", False)),
        audit_enabled=bool(audit.get("enabled", True)),
        audit_paths=bool(audit.get("include_paths", True)),
        audit_retention_days=max(1, int(audit.get("retention_days") or 30)),
        max_document_bytes=max(
            1_048_576,
            int(corporate.get("max_document_bytes") or 50 * 1024 * 1024),
        ),
        terminal_block_network=bool(terminal.get("block_network", True)),
        terminal_allowed_commands=tuple(
            str(pattern) for pattern in terminal.get("network_exceptions", [])
            if str(pattern).strip()
        ),
        terminal_denied_patterns=tuple(
            str(pattern)
            for pattern in terminal.get("denied_patterns", [])
            if str(pattern).strip()
        ),
        skill_allow_local_creation=bool(skills.get("allow_local_creation", True)),
        skill_require_broker_signature=bool(
            skills.get("require_broker_signature", True)
        ),
        diagnostics=tuple(diagnostics),
    )


def get_corporate_policy(*, refresh: bool = False) -> CorporatePolicy:
    global _policy_cache
    if _policy_cache is not None and not refresh:
        return _policy_cache
    with _policy_lock:
        if _policy_cache is None or refresh:
            _policy_cache = _build_policy()
        return _policy_cache


def is_corporate_mode() -> bool:
    return get_corporate_policy().enabled


def filter_tool_names(names: Iterable[str]) -> set[str]:
    policy = get_corporate_policy()
    values = set(names)
    if not policy.enabled:
        return values
    return {name for name in values if policy.allows_tool(name)}


def validate_outbound_url(url: str) -> tuple[bool, str]:
    policy = get_corporate_policy()
    if policy.allows_url(url):
        return True, ""
    return False, (
        "Corporate local mode blocks direct outbound network access. "
        "Only Ollama loopback, the approved skill broker, and configured "
        "intranet destinations are permitted."
    )


def audit_resource(value: str) -> str:
    policy = get_corporate_policy()
    if policy.audit_paths:
        return value
    return f"sha256:{hashlib.sha256(value.encode('utf-8')).hexdigest()[:16]}"


def reset_policy_cache() -> None:
    global _policy_cache
    with _policy_lock:
        _policy_cache = None
