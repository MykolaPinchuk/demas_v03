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
- Suite file (7 tasks): `sandbox/swe_tasks.jsonl`
- Outputs:
  - Baseline single: `sandbox/runs/<ts>/`
  - Baseline batch: `sandbox/batch_runs/<ts>/{results.jsonl,summary.csv}`
  - Agent batch: `sandbox/agent_batch_runs/<ts>/{results.jsonl,summary.csv,logs/}`

### Timeouts (defaults; per‑task overrides supported)
- clone=5s, install=20s, test=5s
- Per task JSONL field: `"timeouts": {"clone":...,"install":...,"test":...}`

### Benchmarks and Leaderboard
- Tracked models: `demas/core/models.py` (`TRACKED_MODELS`).
- Full sweep (all tracked models, parallel tasks, auto-append results, auto-normalize best per model when notes contain "full"):
```bash
CHUTES_API_KEY=YOUR_KEY OPENROUTER_API_KEY=YOUR_OR_KEY \
python -m demas.benchmarks.sweep \
  --seeds sandbox/swe_tasks.jsonl \
  --limit 0 \
  --jobs 12 \
  --temperature 0 \
  --notes "full suite, jobs=12, temp=0"
```
- After a sweep (or anytime) you can normalize the leaderboard explicitly:
```bash
python -m demas.benchmarks.append --normalize
```

### Adapter fallback (single run)
- If `--task-id` is not found in `--tasks`/seeds, `swebench_run_one.py` falls back to `sandbox/swe_official.jsonl` via the SWE adapter.

### Quick validation (smoke)
- Baseline batch (2 tasks):
```bash
python swebench_batch.py --seeds sandbox/swe_tasks.jsonl --limit 2
```
- Agent batch (2 tasks):
```bash
python swebench_batch.py --seeds sandbox/swe_tasks.jsonl --limit 2 --agent
```
- Parallel agent batch (example with 12 workers):
```bash
python swebench_batch.py --seeds sandbox/swe_tasks.jsonl --limit 2 --agent --jobs 12
```

### Benchmarks auto-append
- Full agent suite runs (`--agent` with `--limit 0`) auto-append a row to `BENCHMARKS.md`.
- Add notes (and leaderboard eligibility) with:
```bash
python swebench_batch.py --seeds sandbox/swe_tasks.jsonl --agent --limit 0 --bench-notes "full suite, jobs=12, temp=0.2"
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


