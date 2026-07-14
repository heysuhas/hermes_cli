"""Employee-facing corporate launcher for SR Agent.

This module intentionally does not expose the general ``sr`` command parser.
It is the entry point installed as ``sr-corporate.exe`` for managed Windows
workstations: first launch runs the provider/model setup flow, then every
launch enters interactive chat with a fixed, no-argument invocation.
"""

from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path
from typing import Any


_SETUP_MARKER = ".corporate-setup-complete"
_CONFIG_DIGEST = ".corporate-config.sha256"
_ENV_DIGEST = ".corporate-env.sha256"


def _home() -> Path:
    from sr_constants import get_sr_home

    return get_sr_home()


def _config_path() -> Path:
    return _home() / "config.yaml"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_sealed() -> bool:
    return (_home() / _SETUP_MARKER).exists() and (_home() / _CONFIG_DIGEST).exists()


def _verify_sealed_config() -> None:
    """Fail closed when a user or process changes the managed config file."""
    config_path = _config_path()
    digest_path = _home() / _CONFIG_DIGEST
    if not config_path.exists() or not digest_path.exists():
        raise RuntimeError("SR corporate configuration is incomplete; contact IT support.")
    expected = digest_path.read_text(encoding="ascii").strip().lower()
    actual = _digest(config_path)
    if len(expected) != 64 or expected != actual:
        raise RuntimeError(
            "SR corporate configuration was changed outside the SR setup flow. "
            "Contact IT support to repair this installation."
        )

    env_path = _home() / ".env"
    env_digest_path = _home() / _ENV_DIGEST
    if env_digest_path.exists():
        if not env_path.exists() or env_digest_path.read_text(encoding="ascii").strip().lower() != _digest(env_path):
            raise RuntimeError(
                "SR corporate credentials were changed outside the SR setup flow. "
                "Contact IT support to repair this installation."
            )


def _seal_config() -> None:
    """Persist an integrity marker and make the YAML read-only where possible."""
    home = _home()
    config_path = _config_path()
    digest_path = home / _CONFIG_DIGEST
    digest_path.write_text(_digest(config_path) + "\n", encoding="ascii")

    env_path = home / ".env"
    if env_path.exists():
        (home / _ENV_DIGEST).write_text(_digest(env_path) + "\n", encoding="ascii")

    # The launcher/runtime write guard is authoritative for SR code. These file
    # attributes are defense in depth for normal Explorer/editor attempts.
    for path in (config_path, env_path):
        if not path.exists():
            continue
        try:
            if os.name == "nt":
                import ctypes

                ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x1)  # FILE_ATTRIBUTE_READONLY
            else:
                path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        except (AttributeError, OSError):
            pass


def _unseal_config() -> None:
    for path in (_config_path(), _home() / ".env"):
        if not path.exists():
            continue
        try:
            if os.name == "nt":
                import ctypes

                ctypes.windll.kernel32.SetFileAttributesW(str(path), 0x80)  # FILE_ATTRIBUTE_NORMAL
            else:
                path.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except (AttributeError, OSError):
            pass


def _setup() -> bool:
    """Run the only employee-editable setup flow: provider and model choice."""
    from sr_cli.config import ensure_sr_home, load_config
    from sr_cli.setup import setup_model_provider

    ensure_sr_home()
    _unseal_config()
    os.environ["SR_CORPORATE_CONFIG_WRITE"] = "1"
    try:
        config: dict[str, Any] = load_config()
        setup_model_provider(config, quick=True)
        config = load_config()
        model = config.get("model")
        configured = isinstance(model, dict) and bool(
            str(model.get("provider") or "").strip()
            and str(model.get("default") or model.get("model") or "").strip()
        )
        if not configured:
            print("\nSR setup was not completed. Please restart SR to try again.")
            return False
        (_home() / _SETUP_MARKER).write_text("1\n", encoding="ascii")
        _seal_config()
        return True
    finally:
        os.environ.pop("SR_CORPORATE_CONFIG_WRITE", None)


def _bind_managed_home() -> None:
    """Bind corporate state to the home containing this installed venv."""
    if os.name != "nt":
        return
    try:
        # <SR_HOME>/sr-agent/venv/Scripts/python.exe
        executable = Path(sys.executable).resolve()
        install_root = executable.parents[2]
        if (install_root / ".corporate-install").exists():
            os.environ["SR_HOME"] = str(install_root.parent)
    except (IndexError, OSError):
        pass


def main() -> None:
    """Run the fixed employee experience; reject all user arguments."""
    _bind_managed_home()
    if len(sys.argv) != 1:
        print("SR is managed by your organization and does not accept command-line arguments.")
        print("Launch SR from the Start Menu or desktop shortcut.")
        raise SystemExit(2)

    os.environ["SR_CORPORATE_MODE"] = "1"
    try:
        if _is_sealed():
            _verify_sealed_config()
        elif not _setup():
            raise SystemExit(1)

        # Import only after corporate mode is set so all runtime modules see
        # the policy before tool and slash-command registries are initialized.
        from sr_cli.main import main as run_sr

        run_sr()
    except RuntimeError as exc:
        print(f"\nSR cannot start: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
