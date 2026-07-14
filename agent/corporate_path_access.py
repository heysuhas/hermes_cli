"""Interactive, administrator-bounded grants for corporate local paths."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent.corporate_events import ComplianceEvent, record_compliance
from agent.corporate_policy import CorporatePolicy, get_corporate_policy


_ONCE_GRANT_SECONDS = 300
_grant_lock = threading.RLock()


@dataclass(frozen=True)
class _PathGrant:
    root: Path
    expires_at: float | None


_session_grants: dict[str, list[_PathGrant]] = {}


def _session_key() -> str:
    try:
        from tools.approval import get_current_session_key

        return get_current_session_key(default="local-cli") or "local-cli"
    except Exception:
        return "local-cli"


def _canonical(value: str | Path) -> Path:
    return Path(value).expanduser().resolve(strict=False)


def _contains(root: Path, target: Path) -> bool:
    return target == root or target.is_relative_to(root)


def _live_grants(session_key: str | None = None) -> tuple[Path, ...]:
    key = session_key or _session_key()
    now = time.time()
    with _grant_lock:
        current = _session_grants.get(key, [])
        live = [
            grant
            for grant in current
            if grant.expires_at is None or grant.expires_at > now
        ]
        if live:
            _session_grants[key] = live
        else:
            _session_grants.pop(key, None)
        return tuple(grant.root for grant in live)


def effective_allowed_roots(
    policy: CorporatePolicy | None = None,
    *,
    session_key: str | None = None,
) -> tuple[Path, ...]:
    policy = policy or get_corporate_policy()
    return tuple(dict.fromkeys((*policy.allowed_roots, *_live_grants(session_key))))


def is_path_allowed(
    value: str | Path,
    policy: CorporatePolicy | None = None,
    *,
    session_key: str | None = None,
) -> bool:
    policy = policy or get_corporate_policy()
    if not policy.enabled:
        return True
    target = _canonical(value)
    return any(
        _contains(root, target)
        for root in effective_allowed_roots(policy, session_key=session_key)
    )


def _format_roots(roots: tuple[Path, ...]) -> str:
    if not roots:
        return "(none)"
    return ", ".join(str(root) for root in roots)


def path_access_error(
    value: str | Path,
    policy: CorporatePolicy | None = None,
) -> str:
    policy = policy or get_corporate_policy()
    target = _canonical(value)
    roots = effective_allowed_roots(policy)
    parents = policy.allowed_root_parents
    parent_note = (
        f" Administrator-approved parent directories: {_format_roots(parents)}."
        if parents
        else ""
    )
    return (
        f"Corporate policy blocked `{target}` because it is outside the approved "
        f"working roots. Current roots: {_format_roots(roots)}.{parent_note} "
        "The user must approve the folder in Hermes or run "
        "`hermes corporate roots add <folder>` from a separate user-controlled "
        "shell. The agent must not run that authorization command itself."
    )


def _grant_for_session(root: Path, *, once: bool) -> None:
    expires_at = time.time() + _ONCE_GRANT_SECONDS if once else None
    key = _session_key()
    with _grant_lock:
        grants = _session_grants.setdefault(key, [])
        grants[:] = [grant for grant in grants if grant.root != root]
        grants.append(_PathGrant(root=root, expires_at=expires_at))


def _persist_root(root: Path) -> None:
    from hermes_cli.config import load_config, save_config

    config = load_config()
    product = config.setdefault("product", {})
    roots = product.setdefault("allowed_roots", [])
    canonical = [
        str(_canonical(value))
        for value in roots
        if isinstance(value, (str, Path)) and str(value).strip()
    ]
    if str(root) not in canonical:
        canonical.append(str(root))
    product["allowed_roots"] = canonical
    save_config(config)
    from agent.corporate_policy import reset_policy_cache

    reset_policy_cache()


def request_path_access(
    value: str | Path,
    *,
    purpose: str,
    grant_root: str | Path | None = None,
) -> str | None:
    """Return None when access is permitted, otherwise a user-facing error.

    Interactive approval choices map naturally to path grants:
    ``once`` is a short-lived grant for the current operation, ``session`` is
    process/session-local, and ``always`` persists to the user's config. Every
    grant remains constrained by administrator ``allowed_root_parents``.
    """
    policy = get_corporate_policy()
    if not policy.enabled:
        return None
    target = _canonical(value)
    if is_path_allowed(target, policy):
        return None

    root = _canonical(grant_root) if grant_root else (
        target if target.is_dir() else target.parent
    )
    if not policy.allows_root_selection(root):
        record_compliance(
            ComplianceEvent(
                event_type="path_access",
                action="grant",
                success=False,
                resource=str(target),
                approval="policy_denied",
                policy_violation="outside_admin_root_parents",
                resource_kind="filesystem",
            )
        )
        return path_access_error(target, policy)

    try:
        from tools.approval import prompt_dangerous_approval
        from tools.terminal_tool import _get_approval_callback

        callback = _get_approval_callback()
        if callback is None:
            return path_access_error(target, policy)
        choice = prompt_dangerous_approval(
            command=f"Local folder access: {root}\nRequested path: {target}",
            description=(
                f"Allow Hermes to {purpose}? This grants filesystem access only; "
                "it does not allow network access."
            ),
            allow_permanent=True,
            approval_callback=callback,
        )
    except Exception:
        return path_access_error(target, policy)

    if choice == "once":
        _grant_for_session(target, once=True)
    elif choice == "session":
        _grant_for_session(root, once=False)
    elif choice == "always":
        _persist_root(root)
        policy = get_corporate_policy(refresh=True)
    else:
        record_compliance(
            ComplianceEvent(
                event_type="path_access",
                action="grant",
                success=False,
                resource=str(target),
                approval="denied",
                resource_kind="filesystem",
            )
        )
        return path_access_error(target, policy)

    allowed = is_path_allowed(target, policy)
    record_compliance(
        ComplianceEvent(
            event_type="path_access",
            action="grant",
            success=allowed,
            resource=str(target),
            approval=choice,
            resource_kind="filesystem",
        )
    )
    return None if allowed else path_access_error(target, policy)


def clear_session_path_grants(session_key: str | None = None) -> None:
    with _grant_lock:
        if session_key is None:
            _session_grants.clear()
        else:
            _session_grants.pop(session_key, None)


__all__ = [
    "clear_session_path_grants",
    "effective_allowed_roots",
    "is_path_allowed",
    "path_access_error",
    "request_path_access",
]
