# SR Agent

SR Agent is a local-first AI agent with a Python runtime, terminal interface, gateway services, and a native desktop application.

## Requirements

- Python `>=3.11,<3.14`
- Node.js `>=20`
- npm
- Windows builds: Windows 10/11, WebView2, and the native build tools required by Electron dependencies
- Tauri builds: the Rust toolchain and the platform prerequisites documented by [Tauri](https://tauri.app/start/prerequisites/)

Use the repository launcher; no manual virtual-environment setup is required. It provisions one managed environment and reuses it for both source and packaged runs:

- Windows: `%LOCALAPPDATA%\sr\sr-agent\venv`
- macOS/Linux: `~/.sr/sr-agent/venv`

The launcher installs the managed `uv` tool when needed, creates the environment only when it is missing or incompatible, and synchronizes the current checkout into it.

### Windows PowerShell

```powershell
.\scripts\run-local.ps1
```

Pass agent commands and options after the launcher:

```powershell
.\scripts\run-local.ps1 --help
.\scripts\run-local.ps1 setup
```

### macOS/Linux/WSL

```bash
./scripts/run-local.sh
./scripts/run-local.sh --help
```

Install JavaScript workspace dependencies once before using the desktop client:

```powershell
npm install
npm --workspace apps/desktop run dev
```

The desktop development process uses the same managed environment. If the environment already exists, it is reused rather than creating a repository-local `.venv`.

## Build Windows installers

Run these commands from the repository root. Electron artifacts are written to `apps/desktop/release/`.

```powershell
# Build both NSIS .exe and MSI installers
npm --workspace apps/desktop run dist:win

# Build the NSIS .exe installer only
npm --workspace apps/desktop run dist:win:nsis

# Build the MSI installer only
npm --workspace apps/desktop run dist:win:msi
```

Artifacts use the `SR-<version>-win-<arch>.<ext>` naming pattern.

To build the Tauri bootstrap installer instead:

```powershell
npm --workspace apps/bootstrap-installer run tauri:build
```

Tauri artifacts are written below `apps/bootstrap-installer/src-tauri/target/release/bundle/`, typically in the `msi/` and `nsis/` directories. Use `tauri:build:debug` for a debug bundle.

## Test and validate

Run the desktop checks from the repository root:

```powershell
npm --workspace apps/desktop run typecheck
npm --workspace apps/desktop run test:ui
npm --workspace apps/desktop run test:desktop:platforms
npm --workspace apps/desktop run lint
```

For packaging or first-launch changes, also validate the packaged application:

```powershell
npm --workspace apps/desktop run test:desktop:all
```

The canonical Python test runner is `scripts/run_tests.sh`. Run it from Git Bash, WSL, or another Bash shell:

```bash
scripts/run_tests.sh
```

Run a focused Python test with:

```bash
scripts/run_tests.sh tests/path/to/test_file.py -q
```

From Windows PowerShell, use the shared managed interpreter:

```powershell
& "$env:LOCALAPPDATA\sr\sr-agent\venv\Scripts\python.exe" -m pytest tests/path/to/test_file.py -q
```

Installer builds should be validated on Windows.

## License

MIT — see [`LICENSE`](LICENSE).
