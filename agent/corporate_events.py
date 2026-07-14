"""Versioned local event contracts for corporate telemetry and compliance.

This module defines and locally queues events only. It deliberately contains
no remote exporter; a future intranet collector can consume the two streams
without gaining any control over agent execution.
"""

from __future__ import annotations

import base64
import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from hermes_constants import get_hermes_home

from agent.corporate_policy import audit_resource, get_corporate_policy


EVENT_SCHEMA_VERSION = "hermes.corporate.events.v1"


@dataclass
class OperationalEvent:
    event_type: str
    capability: str
    success: bool
    duration_ms: int = 0
    error_code: str = ""
    tool_name: str = ""
    skill_version: str = ""
    installation_id: str = ""
    application_version: str = ""
    policy_version: str = ""
    model_family: str = ""
    retries: int = 0
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    schema_version: str = EVENT_SCHEMA_VERSION
    stream: Literal["operational"] = "operational"


@dataclass
class ComplianceEvent:
    event_type: str
    action: str
    success: bool
    resource: str = ""
    approval: str = ""
    policy_violation: str = ""
    command_hash: str = ""
    command_classification: str = ""
    tool_name: str = ""
    actor_id: str = ""
    device_id: str = ""
    resource_kind: str = ""
    skill_package_id: str = ""
    skill_version: str = ""
    skill_hash: str = ""
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    schema_version: str = EVENT_SCHEMA_VERSION
    stream: Literal["compliance"] = "compliance"


def _queue_path(stream: str) -> Path:
    return get_hermes_home() / "corporate" / "events" / f"{stream}.jsonl"


def _append(stream: str, payload: dict[str, Any]) -> None:
    policy = get_corporate_policy()
    if not policy.enabled or not policy.audit_enabled:
        return
    path = _queue_path(stream)
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    envelope: dict[str, Any]
    if os.name == "nt":
        try:
            import win32crypt

            protected = win32crypt.CryptProtectData(
                serialized,
                f"Hermes corporate {stream} event",
                None,
                None,
                None,
                0,
            )
            envelope = {
                "schema_version": EVENT_SCHEMA_VERSION,
                "stream": stream,
                "encoding": "windows-dpapi-user",
                "ciphertext": base64.b64encode(protected).decode("ascii"),
            }
        except Exception:
            # Event collection must never break the action being audited.
            return
    else:
        # Non-Windows is development/test-only for this Windows product mode.
        envelope = {
            "schema_version": EVENT_SCHEMA_VERSION,
            "stream": stream,
            "encoding": "json",
            "event": payload,
        }
    line = json.dumps(envelope, ensure_ascii=False, separators=(",", ":")) + "\n"
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)


def record_operational(event: OperationalEvent) -> None:
    _append("operational", asdict(event))


def record_compliance(event: ComplianceEvent) -> None:
    payload = asdict(event)
    if payload.get("resource"):
        payload["resource"] = audit_resource(str(payload["resource"]))
    _append("compliance", payload)
