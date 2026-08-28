# Repository Agent Instructions

## Workspace Instructions

Read the required [workspace instructions](../../../AGENTS.md) before working in this repository. The fixed `KAFKA_PROJECTS_ROOT` layout is required. If the shared file is missing, report a workspace-layout error and stop. The repository-specific rules below supplement and override the shared rules when they conflict.

## Repository Scope

This repository contains the Kafka Adapter modular tests and scripts that assemble the unit-test base configuration from `adapter/base` and `adapter/adapter`. Start with [README.md](README.md). Preserve original Russian 1C identifiers.

The unit-test EDT workspace contains four separate projects: assembled configuration `../base`, test-data extension `../examples`, this modular-test extension, and the YAxUnit core extension in `../yaxunit`. The assembled base combines only `adapter/base` and `adapter/adapter`.

## Repository-Specific Rules

- Use `unit-edt` on port `8768` as the authoritative MCP for live current-state queries, platform-aware navigation, documentation, diagnostics, and every 1C change under `src/**` in the unit-test workspace.
- Use the repository-local `kfk-unit` code-index alias for supplementary read-only analysis of this checkout. When analysis crosses into tested adapter dependencies, reuse `kfk`, `kfk-base`, and `kfk-examples` according to the workspace mapping; they do not replace the local unit alias.
- This repository's `.codex/config.toml` is the only owner of the shared `unit-edt` registration for `../base`, `../examples`, this project, and `../yaxunit`. Do not duplicate that configuration in sibling projects or move it to user Codex configuration.
- Edit assembly scripts and other non-1C configuration directly in UTF-8 within task scope.
- Do not manually edit generated EDT projects, reports, or test output.
- Run focused YAxUnit tests for the changed behavior when the environment is available.
- Do not change adapter, base, examples, or YAxUnit from a unit-test task without explicit multi-repository scope.
