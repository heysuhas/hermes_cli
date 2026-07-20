<p align="center">
  <img src="assets/banner.png" alt="SR Agent" width="100%">
</p>

# SR Agent ☤
<p align="center">
  <a href="https://sr-agent.samsung.com/">SR Agent</a> | <a href="https://sr-agent.samsung.com/">SR Desktop</a>
</p>
<p align="center">
  <a href="https://sr-agent.samsung.com/docs/"><img src="https://img.shields.io/badge/Docs-sr--agent.samsung.com-FFD700?style=for-the-badge" alt="Documentation"></a>
  <a href="https://discord.gg/SamsungResearch"><img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://github.com/SamsungResearch/sr-agent/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://samsung.com"><img src="https://img.shields.io/badge/Built%20by-Nous%20Research-blueviolet?style=for-the-badge" alt="Built by Samsung Research"></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/Lang-中文-red?style=for-the-badge" alt="中文"></a>
  <a href="README.ur-pk.md"><img src="https://img.shields.io/badge/Lang-اردو-green?style=for-the-badge" alt="اردو"></a>
  <a href="README.es.md"><img src="https://img.shields.io/badge/Lang-Español-orange?style=for-the-badge" alt="Español"></a>
</p>

**The self-improving AI agent built by [Samsung Research](https://samsung.com).** It's the only agent with a built-in learning loop — it creates skills from experience, improves them during use, nudges itself to persist knowledge, searches its own past conversations, and builds a deepening model of who you are across sessions. Run it on a $5 VPS, a GPU cluster, or serverless infrastructure that costs nearly nothing when idle. It's not tied to your laptop — talk to it from Telegram while it works on a cloud VM.

Use any model you want — [Nous Portal](https://portal.samsung.com), OpenRouter, OpenAI, your own endpoint, and [many others](https://sr-agent.samsung.com/docs/integrations/providers). Switch with `sr model` — no code changes, no lock-in.

<table>
<tr><td><b>A real terminal interface</b></td><td>Full TUI with multiline editing, slash-command autocomplete, conversation history, interrupt-and-redirect, and streaming tool output.</td></tr>
<tr><td><b>Lives where you do</b></td><td>Telegram, Discord, Slack, WhatsApp, Signal, and CLI — all from a single gateway process. Voice memo transcription, cross-platform conversation continuity.</td></tr>
<tr><td><b>A closed learning loop</b></td><td>Agent-curated memory with periodic nudges. Autonomous skill creation after complex tasks. Skills self-improve during use. FTS5 session search with LLM summarization for cross-session recall. <a href="https://github.com/plastic-labs/honcho">Honcho</a> dialectic user modeling. Compatible with the <a href="https://agentskills.io">agentskills.io</a> open standard.</td></tr>
<tr><td><b>Scheduled automations</b></td><td>Built-in cron scheduler with delivery to any platform. Daily reports, nightly backups, weekly audits — all in natural language, running unattended.</td></tr>
<tr><td><b>Delegates and parallelizes</b></td><td>Spawn isolated subagents for parallel workstreams. Write Python scripts that call tools via RPC, collapsing multi-step pipelines into zero-context-cost turns.</td></tr>
<tr><td><b>Runs anywhere, not just your laptop</b></td><td>Six terminal backends — local, Docker, SSH, Singularity, Modal, and Daytona. Daytona and Modal offer serverless persistence — your agent's environment hibernates when idle and wakes on demand, costing nearly nothing between sessions. Run it on a $5 VPS or a GPU cluster.</td></tr>
<tr><td><b>Research-ready</b></td><td>Batch trajectory generation, trajectory compression for training the next generation of tool-calling models.</td></tr>
</table>

---

## Quick Install

### Linux, macOS, WSL2, Termux

```bash
curl -fsSL https://sr-agent.samsung.com/install.sh | bash
```

### Windows (native, PowerShell)

> **Heads up:** Native Windows runs SR without WSL — CLI, gateway, TUI, and tools all work natively. If you'd rather use WSL2, the Linux/macOS one-liner above works there too. Found a bug? Please [file issues](https://github.com/SamsungResearch/sr-agent/issues).

Run this in PowerShell:

```powershell
iex (irm https://sr-agent.samsung.com/install.ps1)
```

The installer handles everything: uv, Python 3.11, Node.js, ripgrep, ffmpeg, **and a portable Git Bash** (MinGit, unpacked to `%LOCALAPPDATA%\sr\git` — no admin required, completely isolated from any system Git install). SR uses this bundled Git Bash to run shell commands.

If you already have Git installed, the installer detects it and uses that instead. Otherwise a ~45MB MinGit download is all you need — it won't touch or interfere with any system Git.

> **Android / Termux:** The tested manual path is documented in the [Termux guide](https://sr-agent.samsung.com/docs/getting-started/termux). On Termux, SR installs a curated `.[termux]` extra because the full `.[all]` extra currently pulls Android-incompatible voice dependencies.
>
> **Windows:** Native Windows is fully supported — the PowerShell one-liner above installs everything. If you'd rather use WSL2, the Linux command works there too. Native Windows install lives under `%LOCALAPPDATA%\sr`; WSL2 installs under `~/.sr` as on Linux.

After installation:

```bash
source ~/.bashrc    # reload shell (or: source ~/.zshrc)
sr              # start chatting!
```

### Troubleshooting

#### Windows Defender or antivirus flags `uv.exe` as malware

If your antivirus (Bitdefender, Windows Defender, etc.) quarantines `uv.exe` from the SR `bin` folder (`%LOCALAPPDATA%\sr\bin\uv.exe`), this is a **false positive**. The file is Astral's `uv` — the Rust Python package manager SR bundles to manage its Python environment. ML-based antivirus engines commonly flag unsigned Rust binaries that download and install packages.

**To verify your copy is authentic:**

```powershell
# Install GitHub CLI if needed
winget install --id GitHub.cli

# Login to GitHub
gh auth login

# Run verification
$uv = "$env:LOCALAPPDATA\sr\bin\uv.exe"
$ver = (& $uv --version).Split(' ')[1]
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$zip = "$env:TEMP\uv.zip"
Invoke-WebRequest "https://github.com/astral-sh/uv/releases/download/$ver/uv-x86_64-pc-windows-msvc.zip" -OutFile $zip -UseBasicParsing
gh attestation verify $zip --repo astral-sh/uv
Expand-Archive $zip "$env:TEMP\uv_x" -Force
(Get-FileHash "$env:TEMP\uv_x\uv.exe").Hash -eq (Get-FileHash $uv).Hash
```

If attestation says "Verification succeeded" and the last line prints `True`, you're good.

**To whitelist SR:**
- **Windows Defender:** Run PowerShell as Admin → `Add-MpPreference -ExclusionPath "$env:LOCALAPPDATA\sr\bin"`
- **Bitdefender:** Add an exception in the Bitdefender console (Protection > Antivirus > Settings > Manage Exceptions)
- Whitelist the **folder**, not the file hash — SR updates `uv` and the hash changes every version

For more context, see the upstream Astral reports: [astral-sh/uv#13553](https://github.com/astral-sh/uv/issues/13553), [astral-sh/uv#15011](https://github.com/astral-sh/uv/issues/15011), [astral-sh/uv#10079](https://github.com/astral-sh/uv/issues/10079).

---

## Source checkout development

A cloned checkout bootstraps itself. No manual virtual-environment creation or activation is required:

```powershell
python -m sr_cli.main --help
python -m sr_cli.main
```

The first command installs SR's managed `uv` when needed, creates or reuses the canonical environment, synchronizes the checkout, and then re-runs the command inside that environment. The same environment is shared with the packaged desktop app:

- Windows: `%LOCALAPPDATA%\\sr\\sr-agent\\venv`
- macOS/Linux: `~/.sr/sr-agent/venv`

Install JavaScript workspace dependencies before developing the desktop client:

```powershell
npm install
npm --workspace apps/desktop run dev
```

### Windows desktop builds

From the repository root:

```powershell
# Build both NSIS .exe and MSI installers
npm --workspace apps/desktop run dist:win

# Build only the .exe installer
npm --workspace apps/desktop run dist:win:nsis

# Build only the MSI installer
npm --workspace apps/desktop run dist:win:msi
```

Artifacts are written to `apps/desktop/release/`. A packaged `.exe` bootstraps or reuses the same managed environment on first launch; it does not require a repository-local `.venv`.

---

## Getting Started

```bash
sr              # Interactive CLI — start a conversation
sr model        # Choose your LLM provider and model
sr tools        # Configure which tools are enabled
sr config set   # Set individual config values
sr gateway      # Start the messaging gateway (Telegram, Discord, etc.)
sr setup        # Run the full setup wizard (configures everything at once)
sr claw migrate # Migrate from OpenClaw (if coming from OpenClaw)
sr update       # Update to the latest version
sr doctor       # Diagnose any issues
```

📖 **[Full documentation →](https://sr-agent.samsung.com/docs/)**

---

## Skip the API-key collection — Nous Portal

SR works with whatever provider you want — that's not changing. But if you'd rather not collect five separate API keys for the model, web search, image generation, TTS, and a cloud browser, **[Nous Portal](https://portal.samsung.com)** covers all of them under one subscription:

- **300+ models** — pick any of them with `/model <name>`
- **Tool Gateway** — web search (Firecrawl), image generation (FAL), text-to-speech (OpenAI), cloud browser (Browser Use), all routed through your sub. No extra accounts.

One command from a fresh install:

```bash
sr setup --portal
```

That logs you in via OAuth, sets Nous as your provider, and turns on the Tool Gateway. Check what's wired up any time with `sr portal info`. Full details on the [Tool Gateway docs page](https://sr-agent.samsung.com/docs/user-guide/features/tool-gateway).

You can still bring your own keys per-tool whenever you want — the gateway is per-backend, not all-or-nothing.

---

## CLI vs Messaging Quick Reference

SR has two entry points: start the terminal UI with `sr`, or run the gateway and talk to it from Telegram, Discord, Slack, WhatsApp, Signal, or Email. Once you're in a conversation, many slash commands are shared across both interfaces.

| Action                         | CLI                                           | Messaging platforms                                                              |
| ------------------------------ | --------------------------------------------- | -------------------------------------------------------------------------------- |
| Start chatting                 | `sr`                                      | Run `sr gateway setup` + `sr gateway start`, then send the bot a message |
| Start fresh conversation       | `/new` or `/reset`                            | `/new` or `/reset`                                                               |
| Change model                   | `/model [provider:model]`                     | `/model [provider:model]`                                                        |
| Set a personality              | `/personality [name]`                         | `/personality [name]`                                                            |
| Retry or undo the last turn    | `/retry`, `/undo`                             | `/retry`, `/undo`                                                                |
| Compress context / check usage | `/compress`, `/usage`, `/insights [--days N]` | `/compress`, `/usage`, `/insights [days]`                                        |
| Browse skills                  | `/skills` or `/<skill-name>`                  | `/<skill-name>`                                                                  |
| Interrupt current work         | `Ctrl+C` or send a new message                | `/stop` or send a new message                                                    |
| Platform-specific status       | `/platforms`                                  | `/status`, `/sethome`                                                            |

For the full command lists, see the [CLI guide](https://sr-agent.samsung.com/docs/user-guide/cli) and the [Messaging Gateway guide](https://sr-agent.samsung.com/docs/user-guide/messaging).

---

## Documentation

All documentation lives at **[sr-agent.samsung.com/docs](https://sr-agent.samsung.com/docs/)**:

| Section                                                                                             | What's Covered                                             |
| --------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| [Quickstart](https://sr-agent.samsung.com/docs/getting-started/quickstart)                 | Install → setup → first conversation in 2 minutes          |
| [CLI Usage](https://sr-agent.samsung.com/docs/user-guide/cli)                              | Commands, keybindings, personalities, sessions             |
| [Configuration](https://sr-agent.samsung.com/docs/user-guide/configuration)                | Config file, providers, models, all options                |
| [Messaging Gateway](https://sr-agent.samsung.com/docs/user-guide/messaging)                | Telegram, Discord, Slack, WhatsApp, Signal, Home Assistant |
| [Security](https://sr-agent.samsung.com/docs/user-guide/security)                          | Command approval, DM pairing, container isolation          |
| [Tools & Toolsets](https://sr-agent.samsung.com/docs/user-guide/features/tools)            | 40+ tools, toolset system, terminal backends               |
| [Skills System](https://sr-agent.samsung.com/docs/user-guide/features/skills)              | Procedural memory, Skills Hub, creating skills             |
| [Memory](https://sr-agent.samsung.com/docs/user-guide/features/memory)                     | Persistent memory, user profiles, best practices           |
| [MCP Integration](https://sr-agent.samsung.com/docs/user-guide/features/mcp)               | Connect any MCP server for extended capabilities           |
| [Cron Scheduling](https://sr-agent.samsung.com/docs/user-guide/features/cron)              | Scheduled tasks with platform delivery                     |
| [Context Files](https://sr-agent.samsung.com/docs/user-guide/features/context-files)       | Project context that shapes every conversation             |
| [Architecture](https://sr-agent.samsung.com/docs/developer-guide/architecture)             | Project structure, agent loop, key classes                 |
| [Contributing](https://sr-agent.samsung.com/docs/developer-guide/contributing)             | Development setup, PR process, code style                  |
| [CLI Reference](https://sr-agent.samsung.com/docs/reference/cli-commands)                  | All commands and flags                                     |
| [Environment Variables](https://sr-agent.samsung.com/docs/reference/environment-variables) | Complete env var reference                                 |

---

## Migrating from OpenClaw

If you're coming from OpenClaw, SR can automatically import your settings, memories, skills, and API keys.

**During first-time setup:** The setup wizard (`sr setup`) automatically detects `~/.openclaw` and offers to migrate before configuration begins.

**Anytime after install:**

```bash
sr claw migrate              # Interactive migration (full preset)
sr claw migrate --dry-run    # Preview what would be migrated
sr claw migrate --preset user-data   # Migrate without secrets
sr claw migrate --overwrite  # Overwrite existing conflicts
```

What gets imported:

- **SOUL.md** — persona file
- **Memories** — MEMORY.md and USER.md entries
- **Skills** — user-created skills → `~/.sr/skills/openclaw-imports/`
- **Command allowlist** — approval patterns
- **Messaging settings** — platform configs, allowed users, working directory
- **API keys** — allowlisted secrets (Telegram, OpenRouter, OpenAI, Anthropic, ElevenLabs)
- **TTS assets** — workspace audio files
- **Workspace instructions** — AGENTS.md (with `--workspace-target`)

See `sr claw migrate --help` for all options, or use the `openclaw-migration` skill for an interactive agent-guided migration with dry-run previews.

---

## Contributing

We welcome contributions! See the [Contributing Guide](https://sr-agent.samsung.com/docs/developer-guide/contributing) for development setup, code style, and PR process.

Quick start for contributors from a cloned checkout:

```bash
git clone https://github.com/heysuhas/hermes_cli.git
cd hermes_cli
python -m sr_cli.main --help  # bootstraps or reuses the managed environment
python -m sr_cli.main
scripts/run_tests.sh
```

The first `python -m sr_cli.main` invocation creates the managed environment if
needed. Later source runs and packaged desktop runs reuse it. Do not create or
activate a separate repository-local `.venv`.

---

## Community

- 💬 [Discord](https://discord.gg/SamsungResearch)
- 📚 [Skills Hub](https://agentskills.io)
- 🐛 [Issues](https://github.com/SamsungResearch/sr-agent/issues)
- 🔌 [computer-use-linux](https://github.com/avifenesh/computer-use-linux) — Linux desktop-control MCP server for SR and other MCP hosts, with AT-SPI accessibility trees, Wayland/X11 input, screenshots, and compositor window targeting.
- 🔌 [SRClaw](https://github.com/AaronWong1999/srclaw) — Community WeChat bridge: Run SR Agent and OpenClaw on the same WeChat account.

---

## License

MIT — see [LICENSE](LICENSE).

Built by [Samsung Research](https://samsung.com).
