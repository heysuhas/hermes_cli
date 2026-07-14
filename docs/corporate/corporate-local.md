# Corporate Local mode

`product.mode: corporate_local` turns Hermes into a Windows-local employee
assistant. The effective capability set is the intersection of Hermes'
corporate defaults, `%ProgramData%\Hermes\policy.yaml`, and optional user
restrictions. User configuration cannot widen administrator policy.

## Activation

Install the administrator policy from
[`policy.example.yaml`](policy.example.yaml), then set:

```yaml
product:
  mode: corporate_local
  allowed_roots:
    - D:\CorporateWork\CurrentProject

model:
  provider: ollama
  base_url: http://127.0.0.1:11434/v1
```

For Ollama's OpenAI-compatible endpoint, embed the runtime context in the
model rather than relying only on a request option. Some Ollama versions ignore
per-request `options.num_ctx` on `/v1/chat/completions` and silently load the
model at 4,096 tokens:

```text
FROM gemma4:12b
PARAMETER num_ctx 65536
```

Build it with `ollama create gemma4-hermes:12b -f Modelfile`, select that model
in Hermes, and keep `model.ollama_num_ctx: 65536` aligned with the embedded
value. Hermes also budgets output tokens against the estimated prompt and tool
schema footprint and rejects requests that leave no useful generation room.

Use `hermes corporate status` to inspect the effective fingerprint and
`hermes corporate roots add <path>` to select a root below an
administrator-approved parent. `hermes corporate firewall install` creates
Windows Firewall rules for the Hermes Python runtime, common shells, Node, and
Microsoft Office applications. The rules block Internet destinations while
leaving loopback and intranet routes available.

When an interactive file, document, Outlook-attachment, or Office operation
targets a folder outside the current roots, Hermes opens the normal approval
panel in CLI, TUI, or Desktop:

- **Allow once** grants the folder briefly for the current operation.
- **Allow for session** grants it until the local Hermes session/process ends.
- **Always allow** persists the folder under `product.allowed_roots`.
- **Deny** leaves it blocked.

The panel cannot grant a folder outside administrator
`allowed_root_parents`. Non-interactive sessions fail closed and report the
current roots plus the `hermes corporate roots add <folder>` command.

For managed deployment, the firewall command is a bootstrap aid. Enforce the
same Internet-deny boundary centrally with signed Windows Firewall/WFP,
AppLocker, or WDAC policy so renamed or newly installed child executables
cannot become an egress path. The separately signed broker executable must be
the only process granted public egress.

## Runtime behavior

- Only the corporate-local, Outlook, and Office toolsets are sent to the model.
- Cloud fallbacks, browser/web tools, model catalogs, tool search, lazy
  dependency installation, and unrelated bundled plugins are disabled.
- Terminal commands are subject to administrator deny patterns, existing
  dangerous-command approval, approved-root checks, and network-command
  blocking. Windows Firewall remains authoritative.
- Outlook tools read mail and create/update drafts. No send tool exists.
- Office mutations require a staged plan, explicit approval, backup,
  application, verification, and rollback path.
- Private local skills remain editable and are scanned. Externally sourced
  skills must come from the signed broker.

## Artifact broker contract

Hermes uses a narrow API and never sends arbitrary upstream URLs:

- `GET /v1/catalog`
- `GET /v1/packages/{id}/versions`
- `GET /v1/packages/{id}/{version}/manifest`
- `GET /v1/artifacts/{sha256}`
- `POST /v1/install-events`

V1 manifests use an Ed25519 public key in PEM form. The signature covers the
canonical UTF-8 JSON manifest after removing `signature`, with sorted keys and
compact separators. Required fields include package identity, immutable
version, `artifact_sha256`, approval status, provenance, file metadata,
permissions, scanner results, and approval metadata. Hermes verifies the
signature and artifact hash, validates ZIP paths and sizes, then runs the
existing quarantine scanner before installation.

The broker should fetch only configured upstream catalogs, isolate downloads,
scan and approve immutable versions, cache bundles by hash, and support
revocation. Moving it to an intranet service does not change the client API.

## Tracking contracts (collector not implemented)

The versioned contract is `hermes.corporate.events.v1`.

Operational events contain capability/tool identifiers, success, latency,
error code, policy/application versions, and approved skill versions. They do
not contain prompts, business content, file names, or command text.

Compliance events contain authenticated identity only when supplied by a
future deployment layer, action type, policy-permitted resource identifier,
command hash/classification, approval decision, policy violation, and skill
provenance. Bodies and command text are excluded by default.

The streams are written separately and must remain separately encrypted,
signed, retained, authorized, and exported by any future intranet collector.
The collector is observational and never participates in policy decisions or
tool execution.
