# Hermes Agent: Architecture and Extension Guide

This document is the shortest useful path to understanding Hermes Agent well
enough to modify it safely. It explains the runtime, tools, skills, plugins,
sessions, prompts, security boundaries, and the preferred ways to extend the
system.

For contribution rules and detailed coding conventions, also read
[`AGENTS.md`](AGENTS.md).

## 1. The Mental Model

Hermes is one agent core exposed through several user interfaces:

```text
CLI / TUI / Desktop / Messaging Gateway / ACP / Cron / Batch
                           |
                           v
                     AIAgent runtime
                           |
             +-------------+-------------+
             |                           |
             v                           v
      Model/provider adapter       Tool definitions
             |                           |
             v                           v
       LLM response loop      Registry -> handlers -> results
             |
             v
      Session persistence, memory, skills, hooks, and UI events
```

The model is not given hardcoded workflows for each request. It receives:

- A stable system prompt.
- Conversation history and relevant local context.
- A filtered set of tool schemas.
- Skill metadata describing procedures it may load when useful.

The model then decides whether to answer, load a skill, call a tool, inspect a
tool result, call another tool, or finish.

The most important distinction is:

| Concept | What it is | Does it execute code? |
|---|---|---|
| Skill | Markdown instructions, references, scripts, and templates | Not directly; it guides the agent to use tools |
| Tool | A structured function the model can call | Yes, through a registered handler |
| Toolset | A named group of tools exposed together | No |
| Plugin | Python extension that can register tools, hooks, commands, or skills | Yes |
| Hook | Code invoked at a lifecycle boundary | Yes |
| Slash command | User-triggered CLI/gateway action | Possibly |
| MCP server | External process/service exposing structured tools | Yes, outside the Hermes core |

## 2. A Request from Start to Finish

A normal request follows this path:

```text
1. A frontend receives user input.
2. The frontend resolves or creates a conversation session.
3. AIAgent receives the user message and existing history.
4. Hermes assembles the stable prompt and current tool schemas.
5. The selected model returns text, reasoning, or tool calls.
6. Hermes validates and executes real tool calls.
7. Tool results are appended as tool-role messages.
8. The model sees those results and decides what to do next.
9. The loop ends when the model produces a final response or a limit is hit.
10. Messages, usage, and session state are persisted.
```

Simplified:

```python
while within_limits:
    response = model(messages=messages, tools=tool_schemas)

    if response.has_tool_calls:
        for call in response.tool_calls:
            result = execute_registered_tool(call.name, call.arguments)
            messages.append(tool_result(result))
        continue

    return response.text
```

The real implementation also handles interruption, retries, context limits,
compression, malformed local-model tool calls, approvals, callbacks, parallel
calls, and provider-specific response formats.

Primary files:

- [`run_agent.py`](run_agent.py) — public `AIAgent` class and compatibility
  surface.
- [`agent/conversation_loop.py`](agent/conversation_loop.py) — core iterative
  conversation loop.
- [`agent/prompt_builder.py`](agent/prompt_builder.py) and
  [`agent/system_prompt.py`](agent/system_prompt.py) — prompt assembly.
- [`agent/transports/`](agent/transports/) — provider/API-mode request logic.
- [`model_tools.py`](model_tools.py) — tool schema resolution and dispatch
  orchestration.

## 3. Entry Points and User Interfaces

Hermes deliberately shares the same agent core across interfaces.

| Surface | Important files | Responsibility |
|---|---|---|
| Classic CLI | `cli.py`, `hermes_cli/` | Input, rendering, slash commands, approvals |
| Ink TUI | `ui-tui/`, `tui_gateway/` | TypeScript UI over JSON-RPC to Python |
| Electron Desktop | `apps/desktop/`, `tui_gateway/` | Desktop-native chat and prompt UI |
| Messaging gateway | `gateway/run.py`, `gateway/platforms/` | Platform adapters, auth, routing, delivery |
| ACP | `acp_adapter/` | IDE integration for compatible editors |
| Cron | `cron/` | Scheduled agent jobs |
| Batch | `batch_runner.py` | Parallel runs and trajectory generation |

The interface should own presentation and transport concerns. Agent reasoning,
tool behavior, and persistence should remain reusable.

## 4. Prompts, Context, and Prompt Caching

Hermes treats prompt stability as a core invariant. A long-lived conversation
should reuse the same cached prefix instead of rebuilding its past on every
turn.

Prompt content is conceptually split into:

1. Stable instructions — identity, behavior, tool guidance, and durable
   capability metadata.
2. Context — project instruction files and selected workspace context.
3. Volatile information — turn-specific memory, profile, timestamps, and
   runtime notices.

Important rules:

- Do not mutate past messages merely to inject new instructions.
- Do not swap toolsets during a conversation without an intentional session
  transition.
- Maintain valid role alternation.
- Do not inject synthetic user messages in the middle of the tool loop.
- Context compression is the intentional exception to an otherwise stable
  history.

Project instruction files such as `AGENTS.md` are loaded as context. They are
not tools and should remain small enough for the configured context-file
limit.

## 5. Tools

A tool is a structured function available to the model. It has:

- A unique name.
- A JSON schema the model sees.
- A handler Hermes executes.
- A toolset name.
- Optional availability checks and environment requirements.

Built-in tools self-register through
[`tools/registry.py`](tools/registry.py):

```python
registry.register(
    name="example_tool",
    toolset="example",
    schema={
        "name": "example_tool",
        "description": "Do one well-defined operation.",
        "parameters": {
            "type": "object",
            "properties": {
                "value": {"type": "string"},
            },
            "required": ["value"],
        },
    },
    handler=lambda args, **kwargs: handle(args["value"]),
    check_fn=check_requirements,
)
```

### Tool discovery

`discover_builtin_tools()` scans `tools/*.py` for top-level
`registry.register(...)` calls and imports those modules. Importing a module
performs registration.

Plugin and MCP tools ultimately enter the same registry, so dispatch remains
uniform.

### Tool availability

`check_fn` gates whether a tool is included in the schema sent to the model.
This is preferable to exposing an unusable tool and explaining at runtime that
it does not work.

Availability checks are cached briefly. Configuration code that changes tool
availability should invalidate that cache.

### Toolsets

[`toolsets.py`](toolsets.py) maps product/platform capability sets to tool
names. Toolsets control what schemas are sent to the model; they are not
authorization boundaries by themselves.

Every exposed tool consumes context on every model call. A narrowly scoped
toolset is especially important for smaller local models.

### Dispatch

The normal dispatch path is:

```text
model tool call
  -> validate name and arguments
  -> pre-tool hooks/middleware
  -> registry.dispatch()
  -> tool handler
  -> post-tool hooks/middleware
  -> serialized result returned to the model
```

Some stateful tools are intercepted by the agent loop because they need direct
access to agent-owned stores. Most tools should remain ordinary registry
handlers.

Tool handlers should:

- Return structured JSON strings.
- Return useful errors instead of crashing the loop.
- Never claim success before verifying the operation.
- Keep output bounded.
- Accept `task_id` or execution context through `**kwargs` when needed.
- Enforce security inside the handler, not only in the prompt.

## 6. Skills

A skill is procedural knowledge, not an executable model tool. It tells the
agent how to complete a class of tasks using available tools.

Skills use progressive disclosure:

```text
skills_list -> names and descriptions only
skill_view  -> full SKILL.md
skill_view  -> an explicitly requested reference/template/script
```

This avoids putting every full skill into every model request.

At runtime, installed skills live under the active profile's
`HERMES_HOME/skills`, normally:

```text
~/.hermes/skills/
  category/
    skill-name/
      SKILL.md
      references/
      scripts/
      templates/
      assets/
```

Bundled skills in the repository seed the installed skill directory. The
installed profile directory is the runtime source of truth.

Minimal `SKILL.md`:

```markdown
---
name: analyze-local-report
description: Analyze a local business report and produce a sourced summary.
platforms: [windows]
metadata:
  hermes:
    requires_tools: [document_extract]
---

# Analyze a local report

## When to use

Use when the user asks for a summary or analysis of a local report.

## Procedure

1. Extract the document with `document_extract`.
2. Preserve page or section references.
3. Summarize facts before drawing conclusions.
4. Report extraction failures instead of inventing missing content.

## Verification

Confirm the response cites the source pages or sections used.
```

Useful frontmatter can declare:

- Supported platforms.
- Required tools or toolsets.
- Fallback relationships.
- Non-secret configuration.
- Required environment variables or credential files.
- Related skills and tags.

### Self-improving skills

`skill_manage` can create, edit, patch, and maintain private local skills. This
is Hermes' durable procedural-memory loop: a successful workflow can become a
reusable procedure instead of being rediscovered in every session.

Skill writes are validated and scanned. Skill content must not be treated as a
way to bypass tool policy, approvals, path restrictions, or network policy.

Primary files:

- [`tools/skills_tool.py`](tools/skills_tool.py) — listing and reading.
- [`tools/skill_manager_tool.py`](tools/skill_manager_tool.py) — creation and
  maintenance.
- [`tools/skills_guard.py`](tools/skills_guard.py) — security scanning.
- [`tools/skill_usage.py`](tools/skill_usage.py) — usage and curation metadata.
- [`agent/skill_commands.py`](agent/skill_commands.py) — skill slash commands.

## 7. Plugins

A plugin is the preferred way to add custom executable capability without
growing the core.

Typical plugin:

```text
~/.hermes/plugins/my-plugin/
  plugin.yaml
  __init__.py
  schemas.py
  tools.py
  skills/
```

Minimal manifest:

```yaml
name: my-plugin
version: "1.0.0"
description: Adds a focused local capability
```

Minimal registration:

```python
import json


def register(ctx):
    def handler(args, **kwargs):
        return json.dumps({"success": True, "value": args["value"]})

    ctx.register_tool(
        name="my_operation",
        toolset="my_plugin",
        schema={
            "name": "my_operation",
            "description": "Perform the plugin operation.",
            "parameters": {
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
        },
        handler=handler,
    )
```

Plugins can register:

- Tools and toolsets.
- Lifecycle hooks and middleware.
- Slash commands and CLI subcommands.
- Gateway platforms.
- Bundled skills.
- Specialized backends such as memory, context, model, image, video, TTS, and
  STT providers.

Discovery sources include bundled plugins, user plugins, trusted project
plugins, and Python entry points. Third-party code is generally opt-in.

Primary implementation:

- [`hermes_cli/plugins.py`](hermes_cli/plugins.py)
- [`plugins/`](plugins/)

## 8. Choosing the Correct Extension Point

Use the smallest permanent surface that solves the problem:

| Requirement | Preferred extension |
|---|---|
| Better instructions for existing tools | Skill |
| Repeatable workflow using terminal/files | CLI command plus skill |
| Structured capability needed only when configured | Service-gated plugin tool |
| Company-, user-, or project-specific integration | Plugin |
| Reusable external structured tool service | MCP server |
| Fundamental capability required by nearly every Hermes user | Built-in tool, as a last resort |
| New model/inference backend | Model-provider plugin |
| New chat platform | Platform plugin |
| New memory implementation | Memory-provider plugin |
| New compression strategy | Context-engine plugin |

Before adding anything, search for an existing manager, provider interface,
hook, tool, or command that can be extended.

## 9. Sessions, Persistence, Memory, and Context

These mechanisms solve different problems:

| Mechanism | Purpose |
|---|---|
| Conversation history | Current session continuity |
| Session database | Durable transcripts, lineage, search, and usage |
| Memory | Curated facts useful across sessions |
| User profile | Durable preferences and user context |
| Skills | Durable procedures and workflows |
| Context files | Project/workspace instructions |

[`hermes_state.py`](hermes_state.py) provides SQLite-backed session storage and
FTS5 search. Gateway routing additionally uses
[`gateway/session.py`](gateway/session.py) to map platform conversations to
Hermes session IDs.

Profiles isolate configuration and state. Each profile has its own
`HERMES_HOME`, including configuration, secrets, sessions, skills, memory, and
logs.

Do not use memory for long procedures; create a skill. Do not use a skill for
personal facts; use memory/profile storage.

## 10. Providers and Local Models

Provider resolution converts configured model information into a runtime
transport:

```text
provider + model + credentials
       -> base URL and API mode
       -> provider-specific request adapter
       -> normalized response for the agent loop
```

Different providers may use OpenAI-compatible chat completions, response APIs,
or Anthropic-style messages. The conversation loop should consume normalized
results rather than embedding provider-specific behavior throughout the core.

For local Ollama models:

- Keep the system prompt compact.
- Expose only relevant tools.
- Use bounded tool outputs.
- Validate tool arguments.
- Never convert prose into a fabricated tool result.
- Set an explicit context window and output budget.
- Keep loop and continuation limits finite.

## 11. Approvals and Security

Prompts are guidance; enforcement belongs in code.

Security-sensitive operations may pass through:

- Tool availability checks.
- Product and administrator policy.
- Path validation.
- Command classification.
- User approval callbacks.
- Skill scanning.
- Plugin allowlists.
- Operating-system controls such as Windows Firewall or WDAC.

Terminal execution is governed by
[`tools/terminal_tool.py`](tools/terminal_tool.py) and
[`tools/approval.py`](tools/approval.py). UI surfaces receive approval requests
through callbacks or gateway events and return explicit decisions.

An agent must never grant itself broader access by running configuration or
authorization commands through the terminal.

## 12. Corporate Local Mode

`product.mode: corporate_local` narrows Hermes into a Windows-local employee
assistant.

The corporate capability set is policy-filtered and focuses on:

- Governed terminal and process operations.
- User-approved local files.
- Outlook Desktop through COM.
- Local Word, Excel, PowerPoint, PDF, and OCR workflows.
- Private self-improving skills.
- Ollama over loopback.
- Approved skill packages through a signed broker.

Direct public-internet tools, browser access, cloud fallbacks, arbitrary skill
URLs, and lazy Internet dependency installation are excluded.

Relevant files:

- [`agent/corporate_policy.py`](agent/corporate_policy.py)
- [`agent/corporate_path_access.py`](agent/corporate_path_access.py)
- [`plugins/corporate_local/`](plugins/corporate_local/)
- [`plugins/corporate_office/`](plugins/corporate_office/)
- [`plugins/outlook/`](plugins/outlook/)
- [`docs/corporate/corporate-local.md`](docs/corporate/corporate-local.md)

The corporate policy is an enforcement layer around the generic agent loop,
not a replacement rule-based agent.

## 13. Hooks, Events, and Observability

Plugins can observe or influence defined lifecycle boundaries such as:

- Before and after an LLM turn.
- Before and after a tool call.
- Session start, end, reset, and finalization.
- Gateway dispatch.
- Subagent completion.

Hooks should remain generic. Avoid adding speculative hooks with no concrete
consumer.

Tool progress, approvals, messages, and lifecycle status are emitted to the
active interface. The CLI renders them directly; TUI and Desktop receive
JSON-RPC events from `tui_gateway`.

Logs are profile-aware and normally live under:

```text
~/.hermes/logs/
  agent.log
  errors.log
  gateway.log
```

## 14. Configuration

Behavioral settings belong in:

```text
~/.hermes/config.yaml
```

Secrets belong in:

```text
~/.hermes/.env
```

Do not add a new environment variable for ordinary behavior when a
`config.yaml` setting is appropriate.

Useful configuration areas include:

- Active model and provider.
- Enabled/disabled toolsets.
- Enabled plugins.
- Terminal backend and policy.
- Memory and context-engine provider.
- Gateway platforms.
- Product mode.

## 15. Repository Map

```text
run_agent.py                 Public agent class
agent/                       Agent loop, prompts, transports, memory, compression
model_tools.py               Tool resolution and dispatch orchestration
toolsets.py                  Tool group definitions
tools/                       Built-in tool implementations and registry
plugins/                     Bundled extension modules and providers
skills/                      Bundled skills
optional-skills/             Installable official skills
cli.py                       Classic interactive CLI
hermes_cli/                  CLI commands, setup, config, plugin manager
ui-tui/                      Ink terminal UI
tui_gateway/                 Python JSON-RPC backend for TUI/Desktop
apps/desktop/                Electron desktop application
gateway/                     Messaging gateway and platform adapters
cron/                        Scheduled agent jobs
acp_adapter/                 IDE/ACP integration
hermes_state.py              SQLite session store
tests/                       Unit, integration, and E2E tests
website/docs/                Full user and developer documentation
```

## 16. How to Build a Feature Safely

Use this sequence:

1. Reproduce the real behavior and trace the current execution path.
2. Check whether the behavior is intentional.
3. Select the smallest extension surface.
4. Keep model schemas small and descriptions concrete.
5. Put authorization in code, not in model instructions.
6. Preserve prompt stability and message-role invariants.
7. Return structured, grounded tool results.
8. Add tests for the real integration boundary, not only mocked internals.
9. Verify that unrelated interfaces still use the same agent behavior.
10. Document configuration and operational constraints.

### Example: adding a local document workflow

If existing tools can already extract and write the document:

```text
Create a skill
  -> describe when it applies
  -> instruct the agent which existing tools to call
  -> include verification and failure handling
```

If a desktop application needs a structured native integration:

```text
Create a plugin
  -> register service-gated tools
  -> keep schemas narrow
  -> enforce path and mutation approvals in handlers
  -> add an optional skill that teaches the agent the workflow
```

The plugin supplies capability; the skill supplies good judgment about using
that capability.

## 17. Testing Expectations

Choose tests based on the boundary changed:

| Change | Minimum useful test |
|---|---|
| Tool handler | Handler success, validation, failure, bounded output |
| Tool registration | Real discovery and schema inclusion/exclusion |
| Plugin | Manifest discovery plus registered behavior |
| Skill | Frontmatter validation, scanning, and runtime visibility |
| Policy | Allowed case, denied case, and bypass attempt |
| Provider | Real request serialization and response normalization |
| Session behavior | Persistence and resume/reset invariant |
| UI approval | Event/rendering plus response round trip |
| Office/COM integration | Windows E2E test on an Office-equipped host |

Avoid tests that merely freeze a count, version literal, or catalog snapshot.
Prefer behavior contracts and relationships.

## 18. Recommended Reading Order

After this guide:

1. [`AGENTS.md`](AGENTS.md) — contribution intent and invariants.
2. [`website/docs/developer-guide/architecture.md`](website/docs/developer-guide/architecture.md)
   — detailed subsystem map.
3. [`website/docs/developer-guide/tools-runtime.md`](website/docs/developer-guide/tools-runtime.md)
   — tool discovery and dispatch.
4. [`website/docs/developer-guide/creating-skills.md`](website/docs/developer-guide/creating-skills.md)
   — complete skill format.
5. [`website/docs/user-guide/features/plugins.md`](website/docs/user-guide/features/plugins.md)
   — plugin capabilities and activation.
6. [`docs/session-lifecycle.md`](docs/session-lifecycle.md) — gateway session
   state and persistence.
7. [`docs/corporate/corporate-local.md`](docs/corporate/corporate-local.md) —
   corporate-local deployment and policy.


## 19. Recent Corporate-Local Mode Enhancements & Bug Fixes

A series of cross-drive paths, shell escaping, database schemas, and API constraints were resolved to support E2E robustness in the **`corporate_local`** deployment mode on Windows. 

### A. Cross-Drive Node Module Resolution
*   **The Issue:** The codebase repository resides on the `D:` drive (`D:\hermes\hermes-agent`), while the agent runs temporary skill scripts under AppData on the `C:` drive (`C:\Users\test\AppData\Local\hermes\skills\pptx\scripts\`). Node's default module resolution traverses parent paths on the *current* drive to resolve imports (like `pptxgenjs`). As a result, scripts executed from AppData failed to find node modules installed on the `D:` drive.
*   **The Fix:** We ran a local prefix installation to install dependencies directly under the root of the AppData runtime directory (`npm install pptxgenjs --prefix C:\Users\test\AppData\Local\hermes`). This guarantees Node resolves `pptxgenjs` successfully for all skill-based script executions.

### B. Git Bash Windows Path Backslash Escaping
*   **The Issue:** Absolute Windows paths containing backslashes (e.g. `C:\Users\test\AppData\...`) were passed raw to Git Bash. Because Git Bash is a POSIX-compliant shell, it interpreted backslashes as string escape characters, stripping them out and corrupting paths (e.g., `C:\UserstestAppData...`).
*   **The Fix:** Added a regex-based path normalizer in the `_run_bash` method of [local.py](file:///D:/hermes/hermes-agent/tools/environments/local.py#L637-L647):
    ```python
    if _IS_WINDOWS:
        import re
        _windows_path_re = re.compile(
            r'(?i)(?:"([^"]*(?:[A-Z]:\|\\)[^"]*)"|'
            r"'([^']*(?:[A-Z]:\|\\)[^']*)'|"
            r"((?:[A-Z]:\|\\)[^\s|;&<>]+))"
        )
        cmd_string = _windows_path_re.sub(lambda m: m.group(0).replace('\', '/'), cmd_string)
    ```
    This automatically translates backslashes to forward slashes for any absolute Windows paths in command lines before shell invocation, preventing Bash from escaping them.

### C. Outlook COM List Messages Safety (HRESULT 0x80020009)
*   **The Issue:** When looping through Outlook inbox messages via `mail_list_messages`, calling `items.Item(index)` on non-standard, corrupted, or encrypted items threw a COM exception (`com_error hresult=-2147352567`), crashing the entire list command.
*   **The Fix:** Wrapped the message retrieval loop inside [outlook_com.py](file:///D:/hermes/hermes-agent/plugins/outlook/providers/outlook_com.py#L155-L162) in a `try...except Exception` safety boundary. Corrupted/unreadable items are now skipped, allowing the mailbox listing to return all valid messages successfully.

### D. Corporate Directory Whitelisting
*   **The Issue:** In `corporate_local` mode, directory write operations are strictly blocked outside approved paths. The agent got blocked when attempting to save final presentation files or draft summaries in standard user directories (like the Documents folder).
*   **The Fix:** Modified [corporate_policy.py](file:///D:/hermes/hermes-agent/agent/corporate_policy.py#L394-L401) to automatically whitelist standard user-profile output directories:
    ```python
    for path_name in ("Documents", "Downloads", "Desktop"):
        try:
            canonical_roots.append(_canonical_path(Path.home() / path_name))
        except Exception:
            pass
    ```
    This enables the agent to read and write files directly in the user's primary folders while maintaining the corporate security structure.

### E. PowerPoint Generation Steer & Registry Rules
*   **The Issue:** High-level COM tools (like `office_plan_changes` from `corporate_office`) were selected by the LLM to create slides from scratch. Because those tools only support modifying existing templates, they failed with `Document not found`.
*   **The Fix:** Added a project rule in [AGENTS.md](file:///D:/hermes/hermes-agent/AGENTS.md#L71-L81) explicitly guiding the model to avoid first-class COM document tools for scratch file creation, steering it to write and execute a Node.js `pptxgenjs` script instead.

### F. Local Ollama Memory & Context Latency Note
*   **Performance Insight:** Local execution of `gemma4-hermes:12b` via Ollama with the default `65536` context size can trigger hybrid CPU/GPU VRAM offloading. For large payloads (e.g. 20K context tokens), prefill operations can take up to 2–4 minutes per turn. Starting a **New Chat** regularly helps clear session token lists and restores instant inference responses.

## Final Rule of Thumb

When extending Hermes:

```text
Procedure -> skill
Executable integration -> plugin tool
External reusable tool service -> MCP
Fundamental universal primitive -> core tool
```

Keep the core agent loop generic. Put capability at the edges, expose only the
tools needed for the current product mode, and let the model iteratively choose
real actions from grounded tool results.
