# Repository Agent Instructions

## Workspace Instructions

Read the required [workspace instructions](../../../AGENTS.md) before working in this repository. The fixed `KAFKA_PROJECTS_ROOT` layout is required. If the shared file is missing, report a workspace-layout error and stop. The repository-specific rules below supplement and override the shared rules when they conflict.

## Repository Scope

This repository contains YAxUnit tests and scripts that assemble the local EDT test project from base, adapter, examples, and YAxUnit. Start with [README.md](README.md). Preserve original Russian 1C identifiers.

`../base` (`tests/unit/base` from `KAFKA_PROJECTS_ROOT`) is the assembled base configuration used by these tests. It combines `adapter/base`, `adapter/adapter`, `adapter/examples`, and the YAxUnit unit-testing framework core. Treat it as generated project material, not as an independently maintained source repository.

## Repository-Specific Rules

- Use `kfk-unit-edt` as the authoritative MCP for live current-state queries, platform-aware navigation, documentation, diagnostics, and every 1C change under `src/**`. The shared `code-index` may provide supplementary read-only indexed analysis according to workspace policy; BSL LS is unavailable unless this repository explicitly configures it.
- The repository-local `.codex/config.toml` owns only the shared `kfk-unit-edt` server for the `unit` and generated `base` configurations. Do not move this project-scoped server configuration to user Codex configuration.
- Edit assembly scripts and other non-1C configuration directly in UTF-8 within task scope.
- Do not manually edit generated EDT projects, reports, or test output.
- Run focused YAxUnit tests for the changed behavior when the environment is available.
- Do not change adapter, base, or examples from a unit-test task without explicit multi-repository scope.
