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
- Phase 2 complete: adapter/benchmarks moved under `demas/`; README updated; `.gitignore` updated.
- One‑agent migration complete: implementation in `demas/swe/oneagent.py`; root shim removed; callers invoke `python -m demas.swe.oneagent`.
- Baseline runner moved to `demas/swe/baseline.py`; root `swebench_baseline.py` removed; callers invoke `python -m demas.swe.baseline`.
- Batch runners unified: `swebench_batch.py` supports `--agent`; root `swebench_agent_batch.py` removed.
- Credentials auto‑loading added (env files at `~/.config/demas/credentials.env`, `.env.local`, or `demas/credentials.txt`).
- Benchmarks tooling enhanced: `demas.benchmarks.append` CLI; `demas.benchmarks.sweep` for tracked model sweeps; `BENCHMARKS.md` split into leaderboard (full suites only) and full run log.
- Final validation: single/batch (baseline + agent) pass; outputs and CSVs consistent.

## Next agents
No further refactoring actions required. Core goals achieved: minimal root CLIs, internalized logic, unified batch runner, updated docs.

Optional future improvements (non‑blocking):
- Add config flag for tracked model sets/suites in `demas/core/models.py`.
- Extend sweep to export consolidated markdown/plots.

## Known hiccups and editing tips (for next agents)
- Large single-shot edits to `team_swebench_oneagent.py` and `demas/swe/oneagent.py` caused diff timeouts. Prefer incremental moves:
  - First migrate imports/helpers, then tools, then `main()`.
  - If a full-file rewrite is required, consider replacing the entire file content in one operation.
- Current callers already use the module path: runners invoke `python -m demas.swe.oneagent`.
- Transitional state: `demas/swe/oneagent.py` currently wraps the root file’s `main()`; finish migration by inlining code, validate, then delete the root file.
- After each step, re-run quick validations (single task + 2-task batch) to ensure parity.


