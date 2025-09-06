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


## Status (completed)
- Phase 0 complete: shared IO/summaries; batch scripts refactored; parity validated.
- Phase 1 complete: shared docker exec + config wired into runners; parity validated.
- Phase 2 mostly complete: adapter/benchmarks moved under `demas/`; README updated; `.gitignore` updated.
- Cleanup: removed legacy `repo_validate_docker_v5.py`, removed `append_benchmarks.py` shim, removed `swebench_adapter.py` shim.

## Next agents: implementation checklist
Goal: finish hiding complexity at root while keeping UX intact.

1) One-agent module migration
   - Move the implementation from `team_swebench_oneagent.py` into `demas/swe/oneagent.py`.
   - Ensure `python -m demas.swe.oneagent` runs standalone (no root imports).
   - Update `swebench_run_one.py` and `swebench_agent_batch.py` to continue invoking `python -m demas.swe.oneagent` (already done).
   - Validate: run single agent task and a small agent batch; verify outputs unchanged.
   - Remove `team_swebench_oneagent.py` from repo root once validated.

2) Documentation refresh
   - README: confirm examples reference module path for one-agent where appropriate.
   - Keep only the following CLIs at root: `swebench_run_one.py`, `swebench_batch.py`, `swebench_agent_batch.py`.
   - Verify all references to removed shims are gone.

3) Guards and ignore config
   - Confirm `.gitignore` excludes sandbox outputs and caches; keep task JSONLs tracked.
   - Confirm `context_ignore.md` remains aligned to avoid context bloat.

4) Final validation
   - Baseline batch (limit 2) and agent batch (limit 2) passing, artifacts identical in shape.
   - Optional: append benchmark row via `python -m demas.benchmarks.append`.

## Known hiccups and editing tips (for next agents)
- Large single-shot edits to `team_swebench_oneagent.py` and `demas/swe/oneagent.py` caused diff timeouts. Prefer incremental moves:
  - First migrate imports/helpers, then tools, then `main()`.
  - If a full-file rewrite is required, consider replacing the entire file content in one operation.
- Current callers already use the module path: runners invoke `python -m demas.swe.oneagent`.
- Transitional state: `demas/swe/oneagent.py` currently wraps the root file’s `main()`; finish migration by inlining code, validate, then delete the root file.
- After each step, re-run quick validations (single task + 2-task batch) to ensure parity.


