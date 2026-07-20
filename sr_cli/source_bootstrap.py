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
    env = os.environ.copy()
    env[_BOOTSTRAPPED_ENV] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        item for item in (str(root), env.get("PYTHONPATH", "")) if item
    )
    command = [str(python), "-m", "sr_cli.main", *sys.argv[1:]]
    completed = subprocess.run(command, cwd=root, env=env, check=False)
    raise SystemExit(completed.returncode)
