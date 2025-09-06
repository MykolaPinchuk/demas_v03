SWE-bench Plan (Updated)
## What we’re building

- **Goal**: A fast, reproducible harness to run SWE-bench tasks (GitHub repos at specific commits with tests) in Docker, with two modes:
  - Baseline (no AI): clone → install → run tests → record result.
  - Agent (via Chutes): run tests, diagnose, optionally install missing deps, attempt one minimal code patch, re-run tests → record result.

## Broader context: see vision.md. The project described in this plan should advance up to a broad goal outlined there.

## Constraints
- **Python-only** targets for now.
- Internet allowed only for `git clone` and `pip install` (package download); everything else runs offline.
- Provider: **Chutes** only.
- Aim for ≤30 seconds per run (enforced via per-stage timeouts).

## What we have now (components)
- Docker image `swebench-lite:py3.10` with `pytest`, `numpy`, `pandas` preinstalled.
- Baseline tools:
  - `swebench_baseline.py`: one repo run; timeouts; JSON artifact; optional pre/post tails; optional patch.
  - `swebench_batch.py`: runs multiple seeds; writes JSONL and CSV summary.
  - `sandbox/seed_tasks.jsonl`: small test targets (repo/ref/pytest_k).
- Agent tools:
  - `team_swebench_oneagent.py`: one-agent runner with tools `swe_clone`, `swe_install`, `swe_pytest`, `swe_pytest_full`, `swe_read_file`, `swe_pip_install`, `swe_apply_patch_text`.
  - `swebench_agent_batch.py`: runs agent across seeds; JSONL + CSV summary.

## SWE-bench task schema (local JSONL)
- We’ll use a simple local format compatible with both baseline and agent:
  - **Required**:
    - `task_id`: unique id
    - `repo`: git URL
    - `ref`: commit SHA or branch/tag (empty = default branch)
  - **Optional**:
    - `pytest_k`: string passed to `pytest -k` (empty = full test suite)
    - `patch_b64`: optional base64-encoded unified diff to apply before testing (baseline can use this; agent generates its own patch)
    - `timeouts`: `{clone: int, install: int, test: int}` overrides

Example line:
```json
{"task_id":"ex_numpy_case","repo":"https://github.com/numpy/numpy-financial","ref":"","pytest_k":"","patch_b64":""}
```

## Execution modes
- **Baseline (deterministic)**
  - Clone repo at `ref` → install → run `pytest` (optionally `-k`).
  - Optional: pre-patch test tail + apply `patch_b64` + post-patch test tail.
  - Artifacts: `sandbox/runs/<ts>/{result.json, pytest_tail.txt}`; batch writes `results.jsonl` + `summary.csv`.

- **Agent (one attempt to fix)**
  - Clone → install → run tests → if failing, gather diagnostics → optionally `pip install` missing deps → attempt exactly one unified diff patch → re-run tests.
  - Artifacts: batch writes per-task JSONL + CSV summary with final tail and duration.

## Environment and speed
- Docker: `swebench-lite:py3.10` (Python 3.10 + git + preinstalled `pytest`, `numpy`, `pandas`).
- Timeouts (defaults): clone 5s, install 20s, test 5s (overridable per task).
- Keep logs small; store only the last pytest line (“tail”) and a compact JSON result.

## Metrics and outputs
- Per run (baseline/agent): `{task_id, repo, ref, pytest_k, status, duration_s, tail}`.
- Batch CSV: task rows + footer stats (pass_rate, p50_duration, p95_duration).

## How to add tasks
- Edit `sandbox/seed_tasks.jsonl` (for simple repo smoke tests), or create a new JSONL for SWE-bench-like tasks with `task_id/repo/ref/pytest_k`.
- Run:
  - Baseline, one task: `python swebench_baseline.py --task-id <id>`
  - Baseline, batch: `python swebench_batch.py --seeds <file.jsonl>`
  - Agent, one task: set `CHUTES_API_KEY`, then `python team_swebench_oneagent.py` with `TARGET_REPO`, `TARGET_REF`, `PYTEST_K` env vars
  - Agent, batch: `CHUTES_API_KEY=... python swebench_agent_batch.py --seeds <file.jsonl>`

## Roadmap to SWE-bench (measurable)
- P1: Small set (5–10) SWE-bench-like tasks
  - Add 5–10 pinned tasks (pandas/numpy/lightweight) to `sandbox/swe_tasks.jsonl` with small `-k` filters.
  - Success: batch baseline completes ≤30s per task; CSV shows pass_rate and p50/p95 durations.
- P2: Agent lift over baseline
  - Run agent batch on the same tasks (1 patch attempt). Compare pass_rate vs baseline.
  - Add simple config grid: `model` and `temperature` via CLI/env; include in CSV.
- P3: SWE-bench adapter
  - Implement loader to read official SWE-bench items (repo, commit, test selection) and map into our local schema.
  - Validate at least one official instance end-to-end.
- P4: Logging for analysis
  - Persist full agent transcripts/tool calls per run (JSONL next to results); include provider token usage if available.
- P5: Iteration and meta-updates
  - Manual sweep: adjust prompts/parameters between runs based on prior CSVs.
  - Optional: add a meta-runner to auto-tune a small number of parameters (e.g., temperature, max turns) for higher pass_rate under the 30s cap.

## Notes and guardrails
- Docker caching: reuse `swebench-lite:py3.10`.
- Repo location in container: `/workspace/project`.
- Termination: agent prints only the pytest tail from `swe_pytest`; avoid premature stopping on summaries.
- Keep runs short; prefer `-k` filters for heavy suites.

## Immediate next steps (actionable)
- Add 3–5 more pinned SWE-like tasks to `sandbox/swe_tasks.jsonl` (prefer pandas/numpy repos with fast tests).
- Add a minimal SWE-bench adapter (JSON reader) to populate our schema; dry-run one official item.
- Enable CLI flags for agent config (model, temperature) and include them in CSV summaries.
- Persist per-run agent logs (messages + tool calls) alongside `results.jsonl` for later analysis.

## Quick commands
- Baseline, one task:
  - `python swebench_run_one.py --task-id <id>`
- Baseline, batch:
  - `python swebench_batch.py --seeds sandbox/swe_tasks.jsonl`
- Agent, one task:
  - `CHUTES_API_KEY=... python swebench_run_one.py --task-id <id> --agent`
- Agent, batch:
  - `CHUTES_API_KEY=... python swebench_agent_batch.py --seeds sandbox/swe_tasks.jsonl`

## MAS roadmap (after single‑agent completion)

We will only move to multi‑agent systems after the single‑agent core is complete and rigorously validated. This avoids conflating issues across multiple layers.

Gating criteria before MAS:
- Stable single‑agent runs on the 5–10 task suite within time budgets; reproducible outputs.
- CSV/JSONL artifacts complete and consistent (pass_rate, p50/p95; logs with redaction/truncation).
- Robust install/test flow (timeouts respected; basic auto‑healing for missing deps; clear tails).
- Deterministic behavior for baseline; agent variability bounded by config.

Milestones toward MAS:
- M1 (Now): Single‑agent (current). Harden harness, logging, and small auto‑heals. Establish benchmarks.
- M2: Two‑agent handoff. Add a lightweight reviewer/critic agent that can request diagnostics and approve/deny a single patch attempt.
- M3: Role diversity. Introduce specialized roles (installer, tester, patcher) with restricted toolsets; explicit turn budgets.
- M4: Coordination policy. Compare round‑robin vs leader‑follower; add simple retry/abandon heuristics under the 30s cap.
- M5: Meta‑agent. Periodically tune parameters (temperature, max_turns, tool limits) based on prior CSVs; keep runs fast.

Notes:
- Keep internet usage limited to git/pip/model calls as today.
- Persist per‑run transcripts for MAS, same logging format extended with agent_id/role.