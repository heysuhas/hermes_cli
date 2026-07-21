# SR Agent

SR Agent is a local-first AI agent with a Python runtime, terminal interface, gateway services, and a native desktop application.

## Requirements

- Python `>=3.11,<3.14`
- Node.js `>=20`
- npm
- Windows builds: Windows 10/11, WebView2, and the native build tools required by Electron dependencies
- Tauri builds: the Rust toolchain and the platform prerequisites documented by [Tauri](https://tauri.app/start/prerequisites/)

No manual virtual-environment or `uv` installation is required. The first `python -m sr_cli.main` command bootstraps the managed environment automatically. Use PowerShell or Git Bash on Windows.

## Development setup

From the repository root, install the JavaScript workspace dependencies:

```powershell
npm install
```

The managed Python environment is shared by source runs and the packaged desktop application:

- Windows: `%LOCALAPPDATA%\sr\sr-agent\venv`
- macOS/Linux: `~/.sr/sr-agent/venv`

## Use the agent locally

Start the interactive CLI. On the first run, this installs managed `uv`, creates or reuses the shared virtual environment, installs dependencies, and then starts the CLI:

```powershell
python -m sr_cli.main
```

Show available CLI commands and trigger the same automatic setup:

```powershell
python -m sr_cli.main --help
```

The bootstrap adds the managed CLI directory to PATH automatically. Open a new terminal after the first run so the updated PATH is loaded, then use the short command normally:

```powershell
sr setup
sr --help
```

Start the desktop client in development mode:

```powershell
npm --workspace apps/desktop run dev
```

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

From PowerShell, run the focused test with the shared managed interpreter:

```powershell
& "$env:LOCALAPPDATA\sr\sr-agent\venv\Scripts\python.exe" -m pytest tests/path/to/test_file.py -q
```

Installer builds should be validated on Windows.

## Troubleshooting

### Corporate Proxy / SSL Errors during npm install
If you are behind a corporate proxy and `npm install` fails with an SSL verification error (e.g., `unable to verify the first certificate` inside `node install.js`), you can bypass the check for the current terminal session:

**PowerShell:**
```powershell
$env:NODE_TLS_REJECT_UNAUTHORIZED="0"
npm install
```

**Command Prompt:**
```cmd
set NODE_TLS_REJECT_UNAUTHORIZED=0
npm install
```

### Corporate Proxy / SSL Errors during python -m sr_cli.main
If `python -m sr_cli.main` fails to download Python via `uv` with an `invalid peer certificate: UnknownIssuer` error, you can force `uv` to use the native Windows certificate store (which trusts your corporate proxy):

**PowerShell:**
```powershell
$env:UV_NATIVE_TLS="1"
python -m sr_cli.main
```

**Command Prompt:**
```cmd
set UV_NATIVE_TLS=1
python -m sr_cli.main
```

## License

MIT — see [`LICENSE`](LICENSE).
