## Agents Handout – Getting Started Quickly

This file is a knowledge transfer from old agents to new coding agents which will work on this codebase. It is a responsibility of a current agent near the end of its lifecycle to keep this document up-to-date.

### Credentials (auto‑loaded)
- Provide `CHUTES_API_KEY` in one of:
  - `~/.config/demas/credentials.env`
  - `./.env.local`
  - `./demas/credentials.txt`
- Format: `KEY=VALUE` (e.g., `CHUTES_API_KEY=...`). Comments `#` and blanks allowed. Existing OS env vars take precedence.
 - These files are read automatically at import time by `demas.core.config`, so you can run agent commands without exporting `CHUTES_API_KEY` in your shell if one of the files above is present.
 - Note for this environment: a valid `CHUTES_API_KEY` is already configured in `demas/credentials.txt` and is auto‑loaded. Do not ask the user for the key, and never echo it to logs.

### Python virtual environment (required)
- Always use a local venv:
  - `python3 -m venv .venv && source .venv/bin/activate`
  - `python -m pip install -U pip && python -m pip install -r requirements.txt`

### Entrypoints
- Single task runner: `swebench_run_one.py`
  - Baseline: `python swebench_run_one.py --task-id <id>`
  - Agent: `python swebench_run_one.py --task-id <id> --agent`
- Batch runner (unified): `swebench_batch.py`
  - Baseline: `python swebench_batch.py --seeds sandbox/swe_tasks.jsonl [--jobs N]`
  - Agent: `python swebench_batch.py --seeds sandbox/swe_tasks.jsonl --agent [--jobs N]`
- Module CLIs (internals):
  - Baseline: `python -m demas.swe.baseline`
  - Agent: `python -m demas.swe.oneagent`

### Docker
- Image: `swebench-lite:py3.10`
- If missing, the agent runner auto‑builds from root `Dockerfile.swe`.

### Tasks and Outputs
- Current suite file (8 tasks): `sandbox/swe_tasks.jsonl`
- Outputs:
  - Baseline single: `sandbox/runs/<ts>/`
  - Baseline batch: `sandbox/batch_runs/<ts>/{results.jsonl,summary.csv}`
  - Agent batch: `sandbox/agent_batch_runs/<ts>/{results.jsonl,summary.csv,logs/}`

### Timeouts (defaults; per‑task overrides supported)
- clone=5s, install=30s, test=5s (see `demas/core/config.py`)
- Per task JSONL field: `"timeouts": {"clone":...,"install":...,"test":...}`

### Important implementation detail (tail parsing)
- Batch/benchmark paths read pytest tails from the agent JSONL logs (tool result of `swe_pytest`/`swe_pytest_auto`) rather than stdout. This avoids misclassifying outcomes when stdout contains wrapper objects.

### Benchmarks and Leaderboard
- Tracked models: `demas/core/models.py` (`TRACKED_MODELS`).
- Full sweep (all tracked models) with dual attempts and Chutes-only option:
```bash
# Chutes-only, attempts=1 and 2 recorded in BENCHMARKS rows
python -m demas.benchmarks.sweep \
  --seeds sandbox/swe_tasks.jsonl \
  --limit 0 \
  --jobs 12 \
  --notes "full suite, attempts=1 and 2, jobs=12, temp=0.2" \
  --chutes-only
```
- Refresh attempts=1 only (to recompute pass_rate with the current 8-task suite):
```bash
python -m demas.benchmarks.sweep \
  --seeds sandbox/swe_tasks.jsonl \
  --limit 0 \
  --jobs 12 \
  --attempts-mode 1 \
  --notes "full suite, attempts=1 refresh, jobs=12, temp=0.2" \
  --chutes-only
```
- Normalize leaderboard to best per model, preferring dual-attempt rows:
```bash
python -m demas.benchmarks.append --normalize --suite-marker "attempts=1 and 2"
```

### Quick validation (smoke)
- Baseline batch (2 tasks):
```bash
python swebench_batch.py --seeds sandbox/swe_tasks.jsonl --limit 2
```
- Agent batch (2 tasks):
```bash
python swebench_batch.py --seeds sandbox/swe_tasks.jsonl --limit 2 --agent
```
- Parallel agent batch example:
```bash
python swebench_batch.py --seeds sandbox/swe_tasks.jsonl --limit 2 --agent --jobs 12
```

### Guardrails
- Sandbox outputs and caches are `.gitignore`d; small JSONL task files are kept.
- `.cursorignore` reduces context bloat for agents.

### Profiling
- Agent run profiling (per-tool durations) to CSV:
```bash
python -m demas.benchmarks.profile --agent-run-dir sandbox/agent_batch_runs/<timestamp>
```
- Baseline run profiling (per-stage durations) to CSV:
```bash
python -m demas.benchmarks.profile --baseline-run-dir sandbox/batch_runs/<timestamp>
```


