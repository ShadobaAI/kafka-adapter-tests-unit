# Repository Agent Instructions

Apply the required [workspace instructions](../../../AGENTS.md). The rules below are this repository's delta and override shared rules on conflict.

## Repository Scope

This repository contains a development-only 1C extension with Kafka Adapter API examples and integration scenarios; it is not a production deployment artifact. Preserve Russian 1C identifiers.

## Repository-Specific Rules

- Use the shared `unit-edt` from `../unit/.codex/config.toml` on port `8768` for authoritative live state, platform documentation, diagnostics, and every persistent 1C mutation in this checkout.
- For supplementary read-only analysis, reuse only the canonical `kfk-examples` code-index alias from `adapter/examples`. Do not index `tests/unit/examples` separately.
- The reused code-index alias never changes the EDT route: all live work remains on `unit-edt`.
- Prefix new repository-owned 1C metadata objects with `кфк_т_`.
- Run relevant adapter scenarios when they cover the change and the environment is available.
