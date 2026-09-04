# Unit-Test EDT Project Instructions

Apply the required [workspace instructions](../../../AGENTS.md). This generated `base` project combines `adapter/base` and `adapter/adapter` for the unit-test EDT workspace.

- Use the shared `unit-edt` from `../unit/.codex/config.toml` on port `8768` for authoritative live state, platform documentation, diagnostics, and every persistent 1C mutation in this project.
- For supplementary read-only analysis, reuse both canonical code-index aliases: `kfk-base` and `kfk`. Do not create or use a separate alias for `tests/unit/base`.
- Reused code-index aliases never change the EDT route: all live work remains on `unit-edt`.
- Do not edit serialized 1C sources through filesystem tools. The assembly script owns regeneration from `adapter/base` and `adapter/adapter`.
