# Repository Agent Instructions

## Workspace Instructions

Read the required [workspace instructions](../../../AGENTS.md) before working in this repository. The fixed `KAFKA_PROJECTS_ROOT` layout is required. If the shared file is missing, report a workspace-layout error and stop. The repository-specific rules below supplement and override the shared rules when they conflict.

## Repository Scope

This repository contains YAxUnit tests and scripts that assemble the local EDT test project from base, adapter, examples, and YAxUnit. Start with [README.md](README.md). Preserve original Russian 1C identifiers.

`../base` (`tests/unit/base` from `KAFKA_PROJECTS_ROOT`) is the assembled base configuration used by these tests. It combines `adapter/base`, `adapter/adapter`, `adapter/examples`, and the YAxUnit unit-testing framework core. Treat it as generated project material, not as an independently maintained source repository.

## Repository-Specific Rules

- Use only `kfk-unit-edt` for current-state queries, navigation, and every 1C change under `src/**`.
- Do not route this project through `kfk_edt`, `conv_edt`, `code-metadata-mcp`, or `graph-metadata-mcp`.
- Edit assembly scripts and other non-1C configuration directly in UTF-8 within task scope.
- Do not manually edit generated EDT projects, reports, or test output.
- Run focused YAxUnit tests for the changed behavior when the environment is available.
- Do not change adapter, base, or examples from a unit-test task without explicit multi-repository scope.
