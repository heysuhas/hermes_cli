# Hermes Agent - Development Guide & Project Status

This document captures the current development status, architectural context, and deployment details for the Hermes Agent.

## Context: Corporate-Local Assistant Architecture

We have implemented the **Corporate-Local Assistant** deployment pattern (`product.mode: corporate_local`), which turns Hermes into a Windows-local employee assistant with highly restricted and governed capabilities.

### Key Outcomes

- **`product.mode: corporate_local`**: Active pattern restricting capabilities to 23 governed local tools.
- **23-Tool Stable Local Schema**: Composed of:
  - Outlook COM integration (reads mail, manages drafts, **no send** capability).
  - Office/PDF extraction and approval-gated, backed-up mutations.
  - Govened terminal & files.
  - Self-improving local skills.
- **No Fallbacks**: No web, browser, cloud, or arbitrary `execute_code` fallbacks are permitted.
- **Governed Terminal**: Restricted with root, network, package-install, and strict command policies.
- **Signed Skill Broker**: Complete signature checking (Ed25519) on manifest, SHA-256 validation of artifact ZIPs, quarantine scanning, offline caching, and revocation support.
- **Prompt Optimizations**: Compact Ollama-oriented prompting and recovery mechanism for missed tool calls.
- **DPAPI-protected Streams**: Versioned compliance and operational event logging encrypted on disk via DPAPI.
- **Windows Firewall Integration**: Active rule deployment capability to block internet access for Python runtime, shells, Node, and Office apps, while keeping loopback/intranet open.
- **Curated Skills**: Specially packaged local corporate skills.

### Documentation & Configuration Templates
- **Deployment Guidance**: [corporate-local.md](file:///D:/hermes/hermes-agent/docs/corporate/corporate-local.md)
- **Policy Template**: [policy.example.yaml](file:///D:/hermes/hermes-agent/docs/corporate/policy.example.yaml)

---

## Current Status & Validation

- **Test Suite**: 187 tests passing.
- **Linting & Code Quality**: Ruff checks fully passing, lockfile current.
- **Schema Enforcement**: Confirmed live corporate-local schema exposes only allowed toolsets with zero prohibited tools.
- **PDF Analysis Fix**: Added native PDF rendering capability using PyMuPDF (`fitz`) to the `vision_analyze` tool. If a PDF is requested, pages (up to 5) are rendered to base64 PNG images and passed directly to the vision/multimodal LLM, resolving the legacy `"Only real image files are supported"` error.

### Pending Items & Next Steps
- **Managed Laptop Validation**: Live Outlook/Office COM and elevated firewall rule E2E require verification on a managed corporate employee laptop.
- **WDAC Policy Enforcements**: Centralized Windows Firewall/WFP or WDAC policy deployment remains necessary to prevent renamed/newly installed child processes from bypassing local boundaries.
