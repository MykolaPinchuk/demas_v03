## Agents Handout – Getting Started Quickly

This file is a knowledge transfer from old agents to new coding agents which will work on this codebase. It is a responsibility of a current agent near the end of its lifecycle to keep this document up-to-date.

### Credentials (auto‑loaded)
- Provide `CHUTES_API_KEY` in one of:
  - `~/.config/demas/credentials.env`
  - `./.env.local`
  - `./demas/credentials.txt`
- Format: `KEY=VALUE` (e.g., `CHUTES_API_KEY=...`). Comments `#` and blanks allowed. Existing OS env vars take precedence.

### Entrypoints
- Single task runner: `swebench_run_one.py`
  - Baseline: `python swebench_run_one.py --task-id <id>`
  - Agent: `python swebench_run_one.py --task-id <id> --agent`
- Batch runner (unified): `swebench_batch.py`
  - Baseline: `python swebench_batch.py --seeds sandbox/swe_tasks.jsonl`
  - Agent: `python swebench_batch.py --seeds sandbox/swe_tasks.jsonl --agent`
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
- Full sweep (all tracked models, 7 tasks, temp=0; appends to BENCHMARKS.md):
```bash
python -m demas.benchmarks.sweep \
  --seeds sandbox/swe_tasks.jsonl \
  --limit 0 \
  --temperature 0 \
  --notes "full 7-task sweep, temp=0"
```
- BENCHMARKS.md:
  - Leaderboard (top table) shows only runs whose notes contain the word `full`.
  - All runs are appended to the Run Log section.

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

### Guardrails
- Sandbox outputs and caches are `.gitignore`d; small JSONL task files are kept.
- `.cursorignore` reduces context bloat for agents.


