# YAxUnit Checkout Instructions

Apply the required [workspace instructions](../../../AGENTS.md). Preserve upstream YAxUnit conventions and keep Kafka-specific integration changes narrowly scoped.

- Use the shared `unit-edt` from `../unit/.codex/config.toml` on port `8768` for authoritative live state, platform documentation, diagnostics, and every persistent 1C mutation in the YAxUnit core extension loaded by the unit-test workspace.
- Use only the repository-local `kfk-yaxunit` code-index alias for supplementary read-only analysis.
- Do not substitute `kfk-unit` or any reused adapter alias for this checkout, and do not let code-index selection change the `unit-edt` route.
- Do not edit serialized 1C sources through filesystem tools. Run focused upstream YAxUnit checks relevant to the change when available.
