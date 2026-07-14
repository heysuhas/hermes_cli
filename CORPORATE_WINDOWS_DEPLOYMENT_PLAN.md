# SR Agent Corporate Windows Deployment Plan

**Status:** Discovery and architecture proposal  
**Scope:** Windows employee workstations, corporate-managed installation, first-run setup, terminal chat, and removal of the developer CLI experience  
**Prepared:** 2026-07-14

## 1. Executive recommendation

Build and distribute a **signed Windows SR Launcher** (`SR-Launcher.exe`) backed by the repository's existing managed installer and runtime layout. Employees should:

1. Install SR through an enterprise deployment package or run the signed installer once.
2. Launch SR from the Start Menu or desktop shortcut.
3. Complete a first-run provider/model setup wizard.
4. Chat in the terminal window opened by SR.
5. Never need to know or invoke `python sr`, `sr setup`, `sr model`, `sr config`, or any other developer command.

The launcher should be the only supported employee entry point. It should start the agent with a fixed, internally selected argument set and reject arbitrary command-line arguments.

The recommended implementation is **not** a raw PyInstaller conversion of the current Python CLI. The repository already has a stronger Windows foundation:

- `%LOCALAPPDATA%\\sr` is the native Windows SR home directory.
- `scripts/install.ps1` provisions Python, uv, Node, Git, dependencies, config, and the managed runtime.
- `apps/bootstrap-installer` is a Tauri-based Windows bootstrap installer with staged progress, cancellation, JSON/non-interactive installation, Windows PowerShell handling, and Windows icons/manifests.
- `apps/desktop` already launches a headless SR backend and has Windows NSIS/MSI packaging, update handling, and backend resolution.
- `sr` currently exposes a large developer/operator CLI through the `sr = "sr_cli.main:main"` entry point.

For the requested first release, use the existing Tauri bootstrapper for installation and add a **corporate console-launch mode** to the installed product. Preserve the full desktop UI as a later option, but do not make employees use it until the organization decides that a graphical chat surface is preferable.

## 2. Important interpretation of “disable commands”

There are two different meanings of “commands” and they must not be conflated:

### 2.1 Disable the employee-facing CLI surface

This is the requested behavior and should be implemented:

- No employee documentation instructs users to run Python, `sr`, PowerShell scripts, uv, npm, or other setup commands.
- No `sr` executable or source checkout is placed on the employee's PATH.
- The launcher accepts no user-supplied subcommands or arbitrary arguments.
- Setup, provider selection, model selection, diagnostics, updates, reset, and sign-out are launcher-owned flows.
- Administrative/operator commands are available only to IT/support through a separate support package or controlled elevation path.
- Double-clicking the installed application always opens the managed SR experience.

### 2.2 Disable agent tool execution

This is a separate security/product decision. The agent may still need to execute tools such as file operations, web requests, or approved terminal actions to perform useful work. Hiding the CLI does **not** make those actions safe by itself.

Corporate policy must explicitly define:

- Whether local shell/terminal tools are enabled at all.
- Which directories the agent may read or write.
- Whether network access is allowlisted.
- Whether code execution, browser automation, MCP servers, messaging, cron, and background services are disabled.
- Whether shell actions require per-action approval, always require approval, or are unavailable.
- Whether employee prompts and tool output may leave the corporate network.

The launcher-only design is a usability and support boundary. It is not a security boundary against a determined local administrator or a user who can copy binaries and invoke Python. Security controls must also be enforced through Windows policy, endpoint management, application signing, ACLs, and backend/provider controls.

## 3. Findings from the current repository

### Existing runtime and configuration

- `pyproject.toml` defines the package as `sr-agent`, requires Python `>=3.11,<3.14`, and exposes:
  - `sr = "sr_cli.main:main"`
  - `sr-agent = "run_agent:main"`
  - `sr-acp = "acp_adapter.entry:main"`
- `sr_cli/main.py` supports interactive chat plus many operational subcommands including setup, model, gateway, cron, doctor, update, uninstall, ACP, and sessions.
- `sr_cli/setup.py` already contains a provider/model setup wizard and stores configuration under the SR home.
- `sr_constants.py` resolves native Windows state to `%LOCALAPPDATA%\\sr`, with `SR_HOME` available as an override.
- The CLI and setup code already account for Windows UTF-8 handling, Windows PTY support, Windows logging, and Windows-specific dependencies.
- `scripts/install.ps1` defaults to `%LOCALAPPDATA%\\sr`, supports `-NonInteractive`, `-Json`, `-Manifest`, stage execution, pinned commits/tags, and an opt-in `-IncludeDesktop` stage.

### Existing Windows packaging surfaces

- `apps/bootstrap-installer` is a Tauri app branded as SR Setup. It resolves a pinned install script, runs installation stages, streams logs, supports cancellation, and can launch a built SR desktop executable.
- `apps/bootstrap-installer/src-tauri/tauri.conf.json` includes Windows icon support and an embedded WebView bootstrapper, but its current bundle targets list does not include an explicit Windows target. This must be verified and corrected for the corporate artifact.
- `apps/desktop` is an Electron application with Windows `nsis` and `msi` targets. It launches `sr serve --host 127.0.0.1 --port 0` as a headless backend and connects to it from the native renderer.
- `apps/desktop/README.md` says prebuilt installers are intended for Windows, and the package has tests for Windows child processes, environment handling, backend probing, bootstrap, update, and NSIS packaging.
- `docker-compose.windows.yml` exists, but Docker Desktop is not recommended for the employee-local first release. It adds operational overhead, image/runtime management, volume permissions, and a larger endpoint support surface.

### Architectural implication

The repository already separates:

1. **Installer/bootstrap orchestration** — Tauri/Rust and PowerShell.
2. **Agent runtime** — Python package and managed virtual environment.
3. **Employee chat surface** — terminal TUI/CLI today, Electron desktop already available.
4. **Persistent state** — `%LOCALAPPDATA%\\sr` and its subdirectories.

The corporate work should extend these boundaries rather than add a second unrelated installer system.

## 4. Target employee experience

### First launch

1. Employee clicks **SR** from Start Menu.
2. `SR-Launcher.exe` verifies that the managed runtime is installed and matches the approved release.
3. If not installed, the launcher runs the staged bootstrap flow with visible progress and no PowerShell window.
4. The launcher opens the setup wizard:
   - Corporate sign-in or device/user enrollment, if required.
   - Approved provider selection, preferably a centrally managed provider first.
   - Model selection from an allowlisted catalog.
   - Consent and data handling notice.
   - Optional workspace/project selection.
   - Tool policy summary and approval behavior.
   - Connectivity test using the same network/auth leg used for chat.
5. The launcher persists configuration and secrets in the approved Windows storage mechanism.
6. The launcher opens a terminal window and starts the fixed interactive chat mode.

### Subsequent launches

1. Employee clicks SR.
2. Launcher validates the installed runtime and policy.
3. If configuration is complete, it opens the terminal chat directly.
4. If configuration is incomplete or invalid, it opens the relevant setup/recovery screen.
5. Updates occur through the launcher or enterprise software distribution, not through an employee command.

### Exit and recovery

- Normal exit returns the user to Windows without leaving a shell process running.
- A friendly support screen exposes a support ID, version, sanitized diagnostics, log location, and “copy report” action.
- It does not expose raw `sr doctor`, `sr config`, or PowerShell instructions to employees.
- Reset and sign-out are launcher-owned actions with confirmation and clear scope: credentials only, configuration only, sessions only, or full local data.

## 5. Proposed architecture

```text
Start Menu / desktop shortcut
              |
              v
     SR-Launcher.exe (signed)
       |                |
       |                +--> policy, version, repair, support UI
       |
       +--> managed runtime under %LOCALAPPDATA%\\sr\\sr-agent
       |        Python venv + SR package + bundled skills
       |
       +--> fixed interactive chat process
                |
                +--> SR runtime with employee-safe policy
                +--> approved model/provider endpoint
                +--> %LOCALAPPDATA%\\sr\\config.yaml, sessions, logs
```

### Launcher responsibilities

- Own installation, repair, update, setup, launch, and support flows.
- Pass a fixed internal invocation; ignore or reject command-line arguments.
- Set `SR_HOME` explicitly for child processes.
- Set a corporate policy path or policy environment values before starting the runtime.
- Prevent duplicate launches with a single-instance lock.
- Capture child exit status and show actionable recovery.
- Avoid exposing API keys in process arguments, logs, or crash reports.
- Use detached/no-console child process flags only where appropriate; for the requested chat mode, create or attach to a deliberate console window rather than an accidental PowerShell window.

### Runtime responsibilities

- Continue to own model calls, sessions, tools, memory, skills, and streaming.
- Run with an employee-safe configuration profile.
- Disable unsupported subcommands in the corporate build or corporate mode.
- Reject unsafe policy overrides supplied through environment variables or local config.
- Keep configuration and session state in the existing SR home layout.

### Policy responsibilities

Use a separately managed, signed, and preferably centrally deployed policy file rather than allowing employees to edit a local YAML file to regain restricted features. Suggested policy categories:

```yaml
# Illustrative shape; not an implementation commitment.
mode: corporate
allowed_providers: [corporate-gateway]
allowed_models: [approved-model-a, approved-model-b]
allow_shell_tool: false
allow_network_tool: true
allow_mcp: false
allow_messaging: false
allow_cron: false
require_tool_approval: true
allowed_working_directories: []
```

The actual policy schema should be designed after the organization's identity, network, and data-governance requirements are known.

## 6. Packaging strategy options

### Option A — Extend existing Tauri bootstrapper plus console launcher: **recommended for phase 1**

Use `apps/bootstrap-installer` as the signed installer/bootstrap experience. Add or generate a small Windows launcher executable that starts the managed SR runtime in a controlled console chat mode.

**Advantages**

- Reuses existing staged installation protocol and PowerShell hardening.
- Reuses `%LOCALAPPDATA%\\sr` and existing marker/log conventions.
- Keeps installer UI and runtime provisioning separate.
- Avoids shipping a full Python interpreter and dependency tree as a fragile one-file bundle.
- Supports pinned release installation and repeatable enterprise deployment.
- Can later launch the existing desktop UI without replacing the installer.

**Work required**

- Define the launcher contract and fixed invocation.
- Add a supported console-launch entry point that does not expose the general parser.
- Add corporate policy loading and enforcement.
- Make the Tauri bundle produce an explicit Windows `.exe`/MSI artifact.
- Add code signing, release metadata, upgrade, repair, and uninstall policy.
- Make first-run setup launcher-owned, or adapt the existing wizard so it is not reachable as a general CLI command.

### Option B — Use existing Electron `apps/desktop`: **recommended if a GUI is acceptable soon**

Distribute the existing SR Desktop NSIS/MSI installer and let its onboarding UI configure the provider/model. This most closely matches the desired “no terminal commands” employee experience, although it does not match the request for a terminal chat window.

**Advantages**

- Already has a native chat surface, onboarding, settings, backend lifecycle, and update path.
- Existing Windows packaging targets are `nsis` and `msi`.
- Existing tests cover many Windows and managed-runtime paths.

**Concerns**

- Electron is a larger endpoint footprint than a small launcher.
- Existing UI may expose capabilities and settings that corporate policy must constrain.
- The product currently resolves multiple backend candidates, including PATH/system runtime fallbacks; corporate mode should narrow this to the managed runtime only.
- It must be verified that all employee-visible settings obey centrally managed policy.

### Option C — PyInstaller/Nuitka single-file EXE: **not recommended initially**

Package the Python CLI and dependencies directly into a single executable.

**Why defer it**

- The runtime includes dynamic imports, optional providers, data files, skills, Node/native components, browser/tool integrations, and subprocess behavior.
- One-file extraction, antivirus reputation, update replacement, and native dependency handling are likely to be fragile on managed Windows endpoints.
- It does not solve policy enforcement or remove the general CLI parser by itself.
- It duplicates the existing managed-runtime/bootstrap work.

A frozen Python runtime can be reconsidered after the corporate command surface, policy model, and supported dependency set are stable.

### Option D — Docker Desktop bundle: **not recommended for employee first release**

The repository supports Windows Docker Compose, but this is better suited to IT/server deployments than individual laptops. It requires Docker Desktop, virtualization, image lifecycle management, volume permissions, and more complicated support diagnostics.

## 7. “No command-line execution” design

The following controls should be implemented together:

### Product controls

- Create an internal `corporate_launch` entry point that accepts no user command grammar.
- Make `SR-Launcher.exe` reject non-empty arguments, or ignore them and log a safe support event.
- Do not install `sr.exe`, `sr-agent.exe`, `sr-acp.exe`, Python, uv, or source files into a user-facing PATH.
- Do not create shell profile modifications for employees.
- Do not expose terminal instructions in normal help, onboarding, or error screens.
- Remove or hide developer commands from corporate help/completion.
- Keep update, uninstall, repair, and diagnostics behind launcher actions.
- Ensure the child runtime cannot switch to a different `SR_HOME`, provider, model, or policy using ordinary user-controlled environment variables.

### Deployment controls

- Install the runtime under a managed directory with ACLs appropriate to the chosen update model.
- Keep mutable per-user state under `%LOCALAPPDATA%\\sr`.
- Deploy the launcher and policy using Intune, Configuration Manager, Group Policy, or the organization's equivalent.
- Use AppLocker/WDAC if the organization requires prevention of alternate executable/script launches. A product-level launcher cannot prevent a local administrator from running Python or copying files.
- Decide whether employees have local administrator rights; this materially changes the threat model.

### Tool controls

- Explicitly disable shell execution until the security review approves it.
- If shell execution is needed, use a restricted tool policy and approval flow rather than assuming that removing `sr` from PATH is sufficient.
- Restrict working directories and prevent access to credential stores, browser profiles, SSH keys, system directories, and unrelated employee data unless explicitly approved.
- Disable MCP installation/configuration for employees in the first release.
- Disable messaging gateway, cron, ACP, migration, arbitrary update, and uninstall paths in corporate mode.

## 8. Configuration and secret handling

### Provider strategy

The first corporate release should prefer one of these models:

1. **Corporate gateway** — the launcher authenticates the employee/device to a company-controlled endpoint; model/API credentials never reach the employee UI.
2. **Managed provider credentials** — centrally provisioned short-lived tokens or device-bound credentials.
3. **User-entered API key** — only if corporate policy permits it; this is the least desirable operational model.

The current setup wizard supports multiple providers and credential flows. Corporate mode should replace the broad provider catalog with an allowlist and should not let a local `config.yaml` re-enable arbitrary providers.

### Storage

- Keep non-secret SR configuration in `%LOCALAPPDATA%\\sr\\config.yaml` where compatible with existing runtime behavior.
- Store tokens using Windows Credential Manager/DPAPI or a corporate secrets broker rather than plain text wherever possible.
- If compatibility requires `.env` or existing auth files, protect them with user ACLs, document the residual risk, and plan a migration.
- Redact tokens from logs, support bundles, crash reports, and child process command lines.
- Define session retention, deletion, backup, and legal hold requirements before rollout.

### Network and data governance

Document and enforce:

- Approved API hosts and TLS requirements.
- Proxy/PAC behavior for corporate networks.
- Whether prompts, file contents, tool results, and telemetry leave the corporate boundary.
- Data residency and provider retention settings.
- Offline behavior and whether local sessions remain usable without the provider.
- Whether diagnostic uploads are disabled by default.

## 9. Release and enterprise distribution plan

### Build pipeline

1. Build from a clean, pinned source revision.
2. Resolve Python/Node/native dependencies from locked and reviewed inputs.
3. Run Python, TypeScript, Electron/Tauri, packaging, and Windows-specific tests.
4. Generate an SBOM and dependency/license report.
5. Produce the installer and launcher for x64 first; add ARM64 after explicit validation.
6. Sign all executable artifacts with the corporate Authenticode certificate.
7. Publish checksums and release provenance.
8. Test installation, upgrade, repair, rollback, uninstall, and offline failure paths on clean Windows 10/11 VMs.

### Distribution artifacts

A likely first release should contain:

- `SR-Setup-<version>-x64.exe` — signed bootstrap installer for interactive installation.
- `SR-<version>-x64.msi` — enterprise deployment artifact if MSI is required by the software-distribution platform.
- Optionally `SR-<version>-x64.exe` — signed launcher/runtime package for direct pilot distribution.
- A machine/user policy template and an IT deployment guide.
- A release manifest containing version, source commit, runtime versions, hashes, and signing metadata.

Whether the installer or MSI installs the launcher directly should be decided after testing Intune/Configuration Manager behavior. The employee should receive a Start Menu shortcut, not a repository folder or shell command instructions.

### Updates

Choose one owner for updates:

- **Enterprise-managed updates:** preferred for corporate fleet control. Disable self-update and let IT deploy approved versions.
- **Launcher-managed updates:** acceptable for pilot users if update packages are signed, pinned, rollback-capable, and policy-controlled.
- **Runtime self-update via `sr update`:** do not expose this to employees.

Do not allow a launcher to download and execute an unverified branch-head PowerShell script in production. Use immutable release commits, signed artifacts, hash verification, and a controlled update channel.

## 10. Phased implementation plan

### Phase 0 — Corporate requirements and threat model

**Deliverables**

- Approved provider and model list.
- Identity/authentication decision.
- Tool capability policy.
- Data classification and retention decision.
- Supported Windows versions and architectures.
- Endpoint management and signing requirements.
- Decision on enterprise-managed versus launcher-managed updates.

**Exit criteria**

- Security, IT, legal/privacy, and product owners sign off on the scope.
- “No commands” is documented as a user-surface restriction plus explicit tool/security controls.

### Phase 1 — Managed console pilot

**Deliverables**

- Corporate launcher with fixed no-argument launch contract.
- Tauri bootstrapper builds a Windows installer artifact.
- Managed runtime is installed under `%LOCALAPPDATA%\\sr\\sr-agent`.
- First-run setup handles only approved providers/models.
- Chat opens in a controlled terminal window.
- General CLI executable is not placed on PATH.
- Corporate policy disables shell/MCP/messaging/cron by default.
- Launcher-owned support and reset flows.
- Signed x64 pilot artifact.

**Exit criteria**

- Clean Windows VM can install and launch without Python, uv, Git, or PowerShell knowledge.
- Existing user can upgrade without losing sessions/configuration.
- Invalid credentials, blocked network, interrupted install, and corrupted runtime have recoverable UI paths.
- Employees cannot reach the developer subcommand menu through the launcher.

### Phase 2 — Enterprise hardening and fleet rollout

**Deliverables**

- MSI/Intune/Configuration Manager deployment tested.
- Authenticode signing and certificate rotation procedure.
- WDAC/AppLocker recommendations or enforcement package where required.
- Central policy deployment and policy versioning.
- Centralized telemetry limited to approved metadata.
- Support bundle workflow with redaction verification.
- Rollback and emergency disable procedure.

**Exit criteria**

- Pilot fleet passes security and endpoint-management review.
- Update rollout can be staged, paused, rolled back, and audited.
- Support can diagnose failures without asking employees to run commands.

### Phase 3 — Optional native GUI

If the terminal experience proves limiting, promote the existing `apps/desktop` surface as the primary employee UI.

**Required work before adoption**

- Corporate mode in Electron backend resolution: managed runtime only.
- Settings/policy enforcement so local UI cannot override centrally managed values.
- Review file browser, terminal/tool surfaces, previews, voice, projects, and update behavior.
- Reuse the same auth, policy, logs, session store, and enterprise distribution model.

### Phase 4 — Additional platforms and advanced capabilities

Only after Windows corporate operation is stable:

- Windows ARM64.
- macOS/Linux corporate packages if needed.
- Approved MCP catalog.
- Controlled shell execution.
- Remote gateway mode.
- Enterprise admin console and fleet health reporting.

## 11. Testing strategy

### Functional tests

- Fresh install with no Python/Node/Git/uv present.
- Fresh install with conflicting system versions already present.
- First-run setup completion and cancellation.
- Provider/model allowlist behavior.
- Credential storage and logout.
- Chat launch, streaming, Ctrl+C/exit, and relaunch.
- Session persistence and reset scopes.
- Offline install using cached artifacts where supported.
- Upgrade with existing sessions/configuration.
- Repair after deleting the managed venv.
- Uninstall with explicit data-retention choice.

### Windows-specific tests

- Windows 10 and supported Windows 11 builds.
- x64 and eventual ARM64.
- Usernames and paths containing spaces, non-ASCII characters, and 8.3 paths.
- Standard user without admin rights.
- Corporate proxy and TLS interception where applicable.
- Defender/EDR scanning and false-positive handling.
- PowerShell 5.1 baseline.
- No flashing console during install; deliberate visible chat console afterward.
- Child process cleanup on launcher close and crash.
- Single-instance behavior.
- Per-user and per-machine installation modes.

### Security tests

- Pass arbitrary launcher arguments and verify they cannot select commands or policy.
- Attempt to override `SR_HOME`, provider, model, policy path, and executable path.
- Attempt to invoke the packaged Python/runtime directly as a standard user.
- Verify ACLs on configuration, credentials, sessions, and logs.
- Verify secrets never appear in process listings, command lines, logs, crash dumps, or support bundles.
- Test prompt injection against shell, file, network, and MCP policies.
- Verify disabled capabilities remain disabled after restart and update.
- Verify unsigned/tampered update artifacts are rejected.

### Existing validation to reuse

- `apps/desktop` already provides platform/backend/bootstrap/update tests and should remain the reference for Windows process behavior.
- Root Windows-footgun checks and Python test suites should run in CI.
- Add launcher-specific tests for argument rejection, policy loading, runtime resolution, install marker handling, and child process lifecycle.

## 12. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Hiding `sr.exe` is treated as a security control | Users may still run copied/runtime binaries | Enforce policy in the runtime, use Windows application control where needed, and define the local-admin threat model |
| PowerShell/network bootstrap is tampered with | Arbitrary code execution during install | Pin immutable commits, verify hashes/signatures, sign installer, prefer bundled release artifacts for production |
| Electron/Tauri/Node/native dependencies increase endpoint footprint | Larger downloads and AV/EDR scrutiny | Pilot the managed runtime, review SBOM, sign all artifacts, avoid unnecessary optional providers |
| Local config can override corporate policy | Data exfiltration or unsafe tools | Separate immutable/admin policy from user preferences and enforce at runtime |
| API keys stored in existing `.env` paths | Credential disclosure | Migrate to Credential Manager/DPAPI or managed short-lived tokens; audit ACLs and redaction |
| Shell tool remains enabled by accident | Local command execution/data access | Default deny, explicit policy tests, approval gate, restricted directories, security review |
| Self-update changes runtime unexpectedly | Inconsistent fleet and supply-chain risk | Disable employee self-update; use staged enterprise releases and rollback |
| Provider outages block all employees | Availability loss | Corporate gateway fallback, approved fallback provider, or clear degraded/offline behavior |
| Existing CLI and desktop have different feature assumptions | Regression or policy bypass | Define one corporate policy contract and test every entry point against it |
| Native Windows terminal behavior varies | Poor first-run/chat UX | Test conhost, Windows Terminal, redirected stdio, UTF-8, PTY, and standard-user environments |

## 13. Decisions still required

Before implementation begins, the project owner should answer:

1. Will employees authenticate with corporate SSO/device identity, a corporate gateway token, or individual provider keys?
2. Which providers, models, regions, and API hosts are approved?
3. Is local shell execution allowed? If yes, what directories and approval model apply?
4. Are sessions and prompts allowed to persist locally? For how long?
5. Is telemetry required, optional, or prohibited?
6. Will IT own updates, or may the launcher update itself?
7. Is a visible terminal definitely required for the pilot, or is the existing native desktop app acceptable?
8. Which Windows versions and architectures are in scope?
9. Do standard employees have local administrator rights?
10. Is preventing direct runtime invocation a policy requirement or only a user-experience requirement?
11. Should employees be able to select among approved models, or should model choice be centrally fixed?
12. What support/reset actions may employees perform without IT assistance?

## 14. Suggested first implementation ticket breakdown

1. **Corporate policy contract:** schema, precedence, immutable/admin values, tests.
2. **Launcher contract:** fixed no-argument entry point, single-instance behavior, runtime resolution, child lifecycle.
3. **Windows bootstrap artifact:** explicit Tauri Windows target, version stamping, signing hook, release manifest.
4. **Managed console launch:** start the existing chat implementation without exposing the general parser or developer help.
5. **Corporate setup flow:** approved provider/model catalog, auth, connectivity test, policy summary.
6. **Secret storage:** Windows Credential Manager/DPAPI integration or approved corporate gateway auth.
7. **Employee-safe configuration:** block unsupported subcommands and unsafe overrides in corporate mode.
8. **Support and repair:** redacted diagnostics, repair/reinstall, reset scopes, offline/error UX.
9. **Enterprise packaging:** MSI/Intune deployment, Start Menu shortcuts, uninstall and upgrade behavior.
10. **Security/QA gate:** threat-model tests, tamper tests, Windows VM matrix, EDR/signing validation.

## 15. Bottom line

The repository already contains most of the difficult Windows plumbing. The next step should be a **corporate mode**, not a wholesale rewrite:

- Keep the managed runtime and `%LOCALAPPDATA%\\sr` state model.
- Reuse the Tauri bootstrap installer and staged PowerShell protocol.
- Add a signed, no-argument employee launcher.
- Make setup and provider/model selection launcher-owned.
- Start a controlled terminal chat for the pilot.
- Remove the developer CLI from the employee PATH and documentation.
- Enforce tool and provider restrictions in runtime policy, not only in the launcher.
- Let enterprise deployment own signing, updates, rollback, and fleet policy.
- Reassess the existing native desktop app as the primary UI after the pilot.

This gives employees the requested `.exe` workflow while preserving a maintainable architecture and leaving room to move to a richer GUI without rebuilding installation, state, authentication, or policy from scratch.
