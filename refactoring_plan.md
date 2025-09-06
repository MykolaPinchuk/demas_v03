## Repository Refactoring Plan (phase 0–2)

Goal: make entrypoints clear for a non‑expert user while hiding internal logic behind a small internal package. Remove duplication without changing behavior or CLIs. No new features.

Principles
- Keep only user‑facing scripts at repo root initially; move shared logic into a `demas/` package.
- Do behavior‑preserving refactors in small steps; validate parity after each step.
- Maintain fast runs and current outputs. No changes to sandbox layout or defaults.

Pain points today
- Many root `.py` scripts with overlapping responsibilities make it unclear what to run.
- Duplication across batch runners: seed loading, CSV summary generation, timeout/env wiring, docker helpers.
- Legacy utility (`repo_validate_docker_v5.py`) overlaps baseline flow.

Target structure (conceptual)
- Root (keep): `README.md`, `Dockerfile.swe`, `requirements.txt`, existing entry scripts as shims for now.
- New package: `demas/`
  - `demas/core/`
    - `io.py` – task schema loaders (seed JSONL), small IO helpers
    - `summaries.py` – CSV writer + simple metrics (pass_rate, p50, p95)
    - `config.py` (later) – timeouts, image names, paths
    - `docker_exec.py` (later) – single docker invocation helper with timeouts
    - `logging_util.py` (later) – truncation, redaction
  - `demas/swe/` (later)
    - `baseline.py`, `agent.py`, `batch.py` – orchestration using core helpers
  - `demas/adapters/` (later)
    - `swebench.py` – move adapter
  - `demas/benchmarks/` (later)
    - `append.py` – move benchmark appender

File mapping (eventual)
- `swebench_run_one.py` → import `demas.swe.baseline/agent` (no CLI change)
- `swebench_baseline.py` → folded into baseline module
- `swebench_batch.py` → use `demas.core.io` + `demas.core.summaries`
- `swebench_agent_batch.py` → use `demas.core.io` + `demas.core.summaries`
- `team_swebench_oneagent.py` → move to `demas/swe/agent.py` later (unchanged behavior)
- `swebench_adapter.py` → `demas/adapters/swebench.py` later
- `append_benchmarks.py` → `demas/benchmarks/append.py` later
- `repo_validate_docker_v5.py` → `legacy/` later or retire after parity validation

Phase plan
- Phase 0 (this iteration):
  - Add `demas/core/io.py` with `load_seed_tasks`.
  - Add `demas/core/summaries.py` with CSV writers for baseline and agent batch.
  - Refactor `swebench_batch.py` and `swebench_agent_batch.py` to import and use these helpers.
  - Validate parity by re‑running tiny batches.
- Phase 1:
  - Extract common docker/timeouts/config into `demas/core` and have root scripts import them (no CLI changes).
  - Optional: mark `repo_validate_docker_v5.py` as legacy.
- Phase 2:
  - Move adapter/benchmarks into package modules and keep thin shims at root.
  - Optionally introduce `scripts/` CLIs later. For now, skip CLI entry points as agreed.

Non‑goals (for now)
- No MAS changes, no new features, no timeout/model default changes, no sandbox changes.

Validation
- Re-run baseline batch (limit 2) and agent batch (limit 2) after refactors.
- Compare: printed tails, statuses, artifact locations, CSV headers/footers.


