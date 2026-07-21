"""Bootstrap a source checkout before importing dependency-heavy CLI modules."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

_BOOTSTRAPPED_ENV = "SR_SOURCE_BOOTSTRAPPED"
_PYTHON_VERSION = "3.11"


def _source_root() -> Path | None:
    root = Path(__file__).resolve().parent.parent
    if (root / "pyproject.toml").is_file() and (root / "sr_cli" / "main.py").is_file():
        return root
    return None


def _sr_home() -> Path:
    configured = os.environ.get("SR_HOME", "").strip()
    if configured:
        return Path(configured).expanduser()
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
        return (Path(local_appdata) if local_appdata else Path.home() / "AppData" / "Local") / "sr"
    return Path.home() / ".sr"


def _venv_python(venv: Path) -> Path:
    relative = Path("Scripts") / "python.exe" if sys.platform == "win32" else Path("bin") / "python"
    return venv / relative




def _ensure_path_entry(entry: Path) -> None:
    """Make the managed CLI directory available now and in future shells."""
    entry_text = str(entry)
    current = os.environ.get("PATH", "")
    entries = [item for item in current.split(os.pathsep) if item]
    if not any(os.path.normcase(item.rstrip("\\/")) == os.path.normcase(entry_text.rstrip("\\/")) for item in entries):
        os.environ["PATH"] = os.pathsep.join([entry_text, *entries])

    if sys.platform == "win32":
        try:
            import winreg

            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                try:
                    persisted = winreg.QueryValueEx(key, "Path")[0] or ""
                except FileNotFoundError:
                    persisted = ""
                persisted_entries = [item for item in persisted.split(";") if item]
                if not any(item.casefold().rstrip("\\/") == entry_text.casefold().rstrip("\\/") for item in persisted_entries):
                    winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, ";".join([entry_text, *persisted_entries]))
                    
                    import ctypes
                    HWND_BROADCAST = 0xFFFF
                    WM_SETTINGCHANGE = 0x001A
                    SMTO_ABORTIFHUNG = 0x0002
                    result = ctypes.c_long()
                    ctypes.windll.user32.SendMessageTimeoutW(
                        HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment", SMTO_ABORTIFHUNG, 1000, ctypes.byref(result)
                    )
        except (OSError, ImportError):
            # The current process still gets the path; locked-down machines may
            # reject persistent user-environment updates.
            pass
        return

    # Login shells read ~/.profile. Keep one managed line and never duplicate it.
    profile = Path.home() / ".profile"
    marker = "# SR Agent managed CLI"
    try:
        existing = profile.read_text(encoding="utf-8") if profile.exists() else ""
        line = f'export PATH="{entry_text}:$PATH"'
        if marker not in existing:
            separator = "" if not existing or existing.endswith("\n") else "\n"
            profile.write_text(f"{existing}{separator}{marker}\n{line}\n", encoding="utf-8")
    except OSError:
        pass


def _is_expected_python(python: Path) -> bool:
    try:
        result = subprocess.run(
            [str(python), "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0 and result.stdout.strip() == _PYTHON_VERSION


def _acquire_lock(lock: Path) -> None:
    deadline = time.monotonic() + 300
    while True:
        try:
            lock.mkdir(parents=True)
            return
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Timed out waiting for SR environment setup lock: {lock}")
            time.sleep(0.25)


def _sync_environment(uv: str, root: Path, venv: Path) -> None:
    env = os.environ.copy()
    env["UV_PROJECT_ENVIRONMENT"] = str(venv)
    command = [uv, "sync", "--project", str(root), "--extra", "all", "--extra", "dev", "--locked"]
    result = subprocess.run(command, cwd=root, env=env, check=False)
    if result.returncode:
        raise RuntimeError(f"SR dependency synchronization failed with exit code {result.returncode}")


def _prepare_environment(root: Path) -> Path:
    home = _sr_home()
    runtime_root = home / "sr-agent"
    venv = runtime_root / "venv"
    runtime_root.mkdir(parents=True, exist_ok=True)

    # Importing managed_uv is safe here: it only uses the standard library and
    # owns the single SR uv location used by the installers and desktop app.
    from sr_cli.managed_uv import ensure_uv

    uv = ensure_uv()
    if not uv:
        raise RuntimeError(f"Unable to install managed uv under {home / 'bin'}")

    lock = runtime_root / ".source-bootstrap.lock"
    _acquire_lock(lock)
    try:
        python = _venv_python(venv)
        if not _is_expected_python(python):
            if venv.exists():
                shutil.rmtree(venv)
            result = subprocess.run([str(uv), "venv", str(venv), "--python", _PYTHON_VERSION], check=False)
            if result.returncode:
                raise RuntimeError(f"Unable to create the SR virtual environment (exit code {result.returncode})")
            python = _venv_python(venv)

        if not python.is_file():
            raise RuntimeError(f"SR virtual environment was not created at {venv}")
        _sync_environment(str(uv), root, venv)
        return python
    finally:
        try:
            lock.rmdir()
        except OSError:
            pass


def ensure_source_runtime() -> None:
    """Re-exec a source checkout inside SR's canonical managed environment."""
    if os.environ.get(_BOOTSTRAPPED_ENV) == "1" or sys.prefix != sys.base_prefix:
        return

    root = _source_root()
    if root is None:
        return

    python = _prepare_environment(root)
    _ensure_path_entry(python.parent)
    env = os.environ.copy()
    env[_BOOTSTRAPPED_ENV] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        item for item in (str(root), env.get("PYTHONPATH", "")) if item
    )
    command = [str(python), "-m", "sr_cli.main", *sys.argv[1:]]
    completed = subprocess.run(command, cwd=root, env=env, check=False)
    raise SystemExit(completed.returncode)
