## Cleanup / Refactor Checklist (next iteration)

- Agent logging
  - Unify log field names and ensure consistent presence (role, content, tool_name, tool_args, tool_result, usage).
  - Add optional verbosity flag to reduce logs during large batches.

- Agent tools
  - Centralize PYTHONPATH in one constant; keep `/workspace/project` and `/workspace/project/src` + deps.
  - Extract pytest command builder into a helper to avoid duplication.
  - Consider a second auto-heal pass for import errors beyond ModuleNotFoundError (e.g., missing submodules).

- CLI polish
  - Improve `--help` messages; document `--model`, `--temperature`, `--max-turns` in README examples.
  - Ensure per-task timeouts are documented and surfaced in outputs when overridden.

- Benchmarks workflow
  - Optional: simple script to run a standard suite for a grid of models and auto-append rows.
  - Keep BENCHMARKS.md concise by moving old sections to dated archives if it grows too long.

- Tasks
  - Review failing tasks (`dateutil`, `attrs`) to confirm they are intended fast-fail cases.
  - Add/update `pytest_k` filters if a task becomes too heavy.
