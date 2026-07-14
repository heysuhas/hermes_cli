# Hermes Agent - Development Guide

Instructions for AI coding assistants and developers working on the hermes-agent codebase.

**Never give up on the right solution.**

## What Hermes Is

Hermes is a personal AI agent running across CLI, messaging gateway (~20 platforms), TUI, and desktop. It is extended primarily through **plugins and skills**, not by growing the core.

Two properties shape almost every design decision:
- **Per-conversation prompt caching is sacred.** Anything that mutates past context, swaps toolsets, or rebuilds the system prompt mid-conversation invalidates that cache and multiplies the user's cost. We do not do it (except context compression).
- **The core is a narrow waist; capability lives at the edges.** Every model tool we add is sent on every API call. Most new capability should arrive as a CLI command + skill, a service-gated tool, or a plugin — not as a core tool.

---

## Contribution Rubric

### What we want
- **Fix real bugs, well.** A good fix reproduces the symptom on current `main`, points to the exact line where it manifests, and fixes the whole bug class.
- **Expand reach at the edges.** Platform adapters, channels, providers, models, and desktop/TUI features are welcome, integrated via config/setup UX.
- **Keep the core narrow.** New model tools are expensive. Prefer: extend existing code → CLI command + skill → service-gated tool (`check_fn`) → plugin → MCP server → core tool.
- **Extend, don't duplicate.** Check if existing infrastructure already covers the use case before adding new managers or hooks.
- **Behavior contracts over snapshots.** Tests should assert invariants, not freeze current values (e.g. model lists, config versions).
- **E2E validation.** Test real execution paths with temp `HERMES_HOME` rather than relying only on mock unit tests.

### What we don't want (rejected even when well-built)
- **Speculative infrastructure.** No hooks, callbacks, or extension points with no concrete consumer.
- **New `HERMES_*` env vars for non-secret config.** `.env` is for secrets only (API keys, passwords). Behavioral settings (timeouts, flags, paths) go in `config.yaml`.
- **New core tools when terminal + file already do the job.**
- **Outbound telemetry / usage attribution without opt-in gating.**
- **Change-detector tests, cache-breaking mid-conversation, and plugins that edit core files.**

### Before you call it a bug — verify the premise
- **Intentional design, not a gap.** A limitation is often deliberate (e.g. independent profiles). Read original commit intent (`git log -p -S "<symbol>"`) before changing behavior.
- **Verify how it actually works.** Trace the real code execution before accepting a bug report's mental model. Verify the exact line that fails.
- **Deliberate omission.** Obvious-looking missing pieces can be intentional to protect boundaries (e.g., missing `__init__.py` in test trees to prevent shadowing).

---

## The Footprint Ladder

Choose the highest (least-footprint) rung that correctly solves the problem:
1. **Extend existing code** — Zero new surface.
2. **CLI command + skill** — Guided by a skill. Zero model-tool footprint. (Default choice for service setups, cron, etc.).
3. **Service-gated tool (`check_fn`)** — Appears only when prerequisite config is present.
4. **Plugin** — Lives in `~/.hermes/plugins/` or a pip package, discovered at runtime.
5. **MCP server (in the catalog)** — Connects via built-in MCP client. Zero permanent core-schema footprint.
6. **New core tool** — Last resort, only when fundamental to almost all users and unreachable via terminal/file.

---

## Python Style & Guidelines

- **No speculative code.** Keep modules focused.
- **Secrets vs Settings.** Keep secrets (tokens, keys) in `.env` / `OPTIONAL_ENV_VARS` in `hermes_cli/config.py`. Non-secret configurations belong in `config.yaml`.
- **Config migrations.** Bump `_config_version` in `hermes_cli/config.py` only if migrating/transforming existing configs.
- **State files.** Use `get_hermes_home()` as the base directory for logs, caches, and checkpoints to respect user profiles (never `Path.home() / ".hermes"`).
- **Plugin rules.** Plugins must never edit core files. If a plugin needs new capability, expand the generic plugin registration surface.

---

## TypeScript Style

- Prefer small nanostores over component state when state is shared or read by distant UI.
- Chat state belongs near chat, shell state near shell, shared state in `src/store`.
- Table-driven code beats condition ladders when mapping routes, views, or IDs.
- Table rendering / Composer / PTY terminal belong to the embedded TUI `hermes --tui`. Extend Ink rather than rewriting chat elements in React.
- React UI around the TUI (sidebars, inspectors, status panels) is encouraged if it doesn't replace the main composer/PTY.

---

## Creating PowerPoint Presentations from Scratch

If the user requests the creation of a PowerPoint presentation (.pptx) from scratch (meaning the target file does not exist yet):
- **Do NOT** call `office_plan_changes` or `document_extract` (these tools only work on existing files and will fail with "Document not found" or unsupported format errors).
- **Instead**, always write and execute a Node.js script using the `pptxgenjs` library to generate the PowerPoint file from scratch (following the instructions in the `pptx` skill's `pptxgenjs.md`).
- Ensure all paths passed to terminal commands use forward slashes (e.g., `C:/Users/test/Documents/test.pptx`) or are quoted to prevent backslash escaping issues in Git Bash.

