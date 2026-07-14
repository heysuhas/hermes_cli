from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from agent import corporate_policy as policy_module
from agent.corporate_policy import CorporatePolicy
from tools import skills_hub


def _skill_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "SKILL.md",
            "---\nname: approved-skill\ndescription: local workflow\n---\nUse local files.",
        )
    return buffer.getvalue()


def test_broker_verifies_signature_hash_and_bundle_paths(monkeypatch, tmp_path):
    private_key = Ed25519PrivateKey.generate()
    public_key_path = tmp_path / "broker-public.pem"
    public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    artifact = _skill_zip()
    artifact_sha = hashlib.sha256(artifact).hexdigest()
    manifest = {
        "package_id": "approved-skill",
        "name": "approved-skill",
        "version": "1.2.3",
        "approved": True,
        "approved_at": "2026-06-25T00:00:00Z",
        "artifact_sha256": artifact_sha,
        "upstream_source": "hermes-official",
        "scanner_results": {"malware": "clean", "policy": "pass"},
    }
    payload = json.dumps(
        manifest, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    manifest["signature"] = base64.b64encode(private_key.sign(payload)).decode()

    monkeypatch.setattr(
        policy_module,
        "_policy_cache",
        CorporatePolicy(
            enabled=True,
            allowed_roots=(tmp_path,),
            broker_url="http://127.0.0.1:8765",
            broker_public_key_file=public_key_path,
            skill_require_broker_signature=True,
            audit_enabled=False,
        ),
    )

    def fake_get(url, **kwargs):
        if url.endswith("/manifest"):
            return httpx.Response(200, json=manifest)
        if url.endswith(artifact_sha):
            return httpx.Response(200, content=artifact)
        raise AssertionError(f"unexpected broker URL: {url}")

    monkeypatch.setattr(skills_hub.httpx, "get", fake_get)

    source = skills_hub.CorporateBrokerSource()
    source.cache_dir = tmp_path / "cache"
    bundle = source.fetch(
        "corporate-broker/approved-skill@1.2.3"
    )

    assert bundle is not None
    assert bundle.source == "corporate-broker"
    assert bundle.metadata["artifact_sha256"] == artifact_sha
    assert "SKILL.md" in bundle.files

    monkeypatch.setattr(skills_hub.httpx, "get", lambda *args, **kwargs: None)
    offline = skills_hub.CorporateBrokerSource()
    offline.cache_dir = source.cache_dir
    cached_bundle = offline.fetch("corporate-broker/approved-skill@1.2.3")
    assert cached_bundle is not None
    assert cached_bundle.metadata["version"] == "1.2.3"


def test_broker_rejects_tampered_artifact(monkeypatch, tmp_path):
    monkeypatch.setattr(
        policy_module,
        "_policy_cache",
        CorporatePolicy(
            enabled=True,
            allowed_roots=(tmp_path,),
            broker_url="http://127.0.0.1:8765",
            skill_require_broker_signature=False,
            audit_enabled=False,
        ),
    )
    expected_sha = hashlib.sha256(b"expected").hexdigest()
    manifest = {
        "package_id": "approved-skill",
        "name": "approved-skill",
        "version": "1.0.0",
        "approved": True,
        "artifact_sha256": expected_sha,
    }

    def fake_get(url, **kwargs):
        if url.endswith("/manifest"):
            return httpx.Response(200, json=manifest)
        return httpx.Response(200, content=b"tampered")

    monkeypatch.setattr(skills_hub.httpx, "get", fake_get)

    assert (
        skills_hub.CorporateBrokerSource().fetch(
            "corporate-broker/approved-skill@1.0.0"
        )
        is None
    )


def test_broker_does_not_use_cache_after_definitive_revocation(monkeypatch, tmp_path):
    artifact = _skill_zip()
    artifact_sha = hashlib.sha256(artifact).hexdigest()
    cache_dir = tmp_path / "cache"
    manifest_path = (
        cache_dir / "manifests" / "approved-skill" / "1.0.0.json"
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(
        json.dumps(
            {
                "package_id": "approved-skill",
                "name": "approved-skill",
                "version": "1.0.0",
                "approved": True,
                "artifact_sha256": artifact_sha,
            }
        ),
        encoding="utf-8",
    )
    artifact_path = cache_dir / "artifacts" / artifact_sha
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_bytes(artifact)
    monkeypatch.setattr(
        policy_module,
        "_policy_cache",
        CorporatePolicy(
            enabled=True,
            allowed_roots=(tmp_path,),
            broker_url="http://127.0.0.1:8765",
            skill_require_broker_signature=False,
            audit_enabled=False,
        ),
    )
    monkeypatch.setattr(
        skills_hub.httpx,
        "get",
        lambda *args, **kwargs: httpx.Response(410),
    )
    source = skills_hub.CorporateBrokerSource()
    source.cache_dir = cache_dir

    assert source.fetch("corporate-broker/approved-skill@1.0.0") is None
