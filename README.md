## DEMAS – Fast Harness for Agentic Coding (SWE-bench style)

This repository is the first step toward a Dynamic Evolutionary Multi‑Agent System (DEMAS) for agentic coding. It provides a fast, reproducible harness to run and evaluate code changes inside Docker, with both a baseline (no AI) mode and an AI agent mode (via Chutes).

Docs map:
- High‑level vision and motivation: `vision.md`
- Roadmap, constraints, and detailed next steps: `plan.md`

### Repo structure (key files)
- Docker and runners (root scripts = stable CLIs; internal logic under `demas/`)
  - `Dockerfile.swe`: Python 3.10 + git + preinstalled `pytest`, `numpy`, `pandas` for speed.
  - `swebench_run_one.py`: run a single SWE‑style task (baseline or `--agent`).
  - `demas/swe/baseline.py`: baseline module runner (invoked via `python -m demas.swe.baseline`).
  - `swebench_batch.py`: supports baseline and `--agent` to run the agent across tasks and summarize. Agent mode supports `--jobs N` for parallel tasks.
  - `demas/swe/oneagent.py`: one‑agent runner (invoked via `python -m demas.swe.oneagent`).
  - Internal package: `demas/` (shared helpers and modules)
    - `demas/core/`: `config.py`, `docker_exec.py`, `io.py`, `summaries.py`
    - `demas/adapters/`: `swebench.py` (SWE‑bench adapter)
    - `demas/benchmarks/`: `append.py` (benchmarks row appender)
- Tasks and outputs
  - `sandbox/seed_tasks.jsonl`: small “seed” repos for quick smoke tests.
  - `sandbox/swe_tasks.jsonl`: SWE‑style tasks (repo + commit + optional `-k`).
  - Outputs: `sandbox/runs/…` (baseline), `sandbox/batch_runs/…`, `sandbox/agent_batch_runs/…`.

### Requirements
- Docker installed and able to run Linux containers.
- Python 3.10+ on host: preferably use a virtual environment.
  - Quick start (venv):
    - `python3 -m venv .venv && source .venv/bin/activate`
    - `python -m pip install -U pip && python -m pip install -r requirements.txt`
  - If you skip venv, ensure your global Python does not conflict with pinned deps.
- Chutes API key for agent mode: set `CHUTES_API_KEY`.
  - Optional: place secrets in `~/.config/demas/credentials.env`, repo-local `.env.local`, or `demas/credentials.txt`:
    - Lines: `KEY=VALUE` (e.g., `CHUTES_API_KEY=...`). Comments `#` and blanks are ignored. Existing env vars are not overridden.
  - These files are auto-loaded by `demas.core.config` on import, so you can run agent commands without exporting `CHUTES_API_KEY` in your shell if any of them is present.
  - Project default: this repository already has a usable `CHUTES_API_KEY` stored in `demas/credentials.txt` on this machine. It is auto-loaded; do not ask the user for the key and never print it in logs.

### Build the Docker image
```bash
docker build -f Dockerfile.swe -t swebench-lite:py3.10 .
```

### Quickstart (baseline)
Run a single task from `sandbox/swe_tasks.jsonl` (pinned repo@commit):
```bash
python swebench_run_one.py --task-id swe_demo_numpy_financial
```
Run a batch and produce summaries:
```bash
python swebench_batch.py --seeds sandbox/swe_tasks.jsonl
```
Artifacts:
- Per run: `sandbox/runs/<timestamp>/{result.json, pytest_tail.txt}`
- Batch: `sandbox/batch_runs/<timestamp>/{results.jsonl, summary.csv}`

### Quickstart (agent)
Single task:
```bash
CHUTES_API_KEY=YOUR_KEY python swebench_run_one.py --task-id swe_demo_numpy_financial --agent
```
Batch:
```bash
CHUTES_API_KEY=YOUR_KEY python swebench_batch.py --seeds sandbox/swe_tasks.jsonl --agent
```
If your key is stored in one of the auto-loaded files above, you can omit the inline environment variable:
```bash
python swebench_run_one.py --task-id swe_demo_numpy_financial --agent
python swebench_batch.py --seeds sandbox/swe_tasks.jsonl --agent
```
Parallel agent batch (example with 12 workers):
```bash
CHUTES_API_KEY=YOUR_KEY OPENROUTER_API_KEY=YOUR_OR_KEY \
python swebench_batch.py --seeds sandbox/swe_tasks.jsonl --agent --jobs 12
```
Notes:
- `--jobs` controls parallelism for both baseline and agent modes. If omitted, the runner auto-selects `max(12, cpu_count - 2)`.
Agent batch outputs:
- `sandbox/agent_batch_runs/<timestamp>/{results.jsonl, summary.csv}` (when using `--agent`)

### Task format
Local JSONL schema used by both baseline and agent:
```json
{"task_id":"id","repo":"https://github.com/org/repo","ref":"<commit-or-branch>","pytest_k":"","patch_b64":"","timeouts":{"clone":5,"install":30,"test":5}}
```
See also `plan.md` for how this schema is used across single and batch runs.

### Notes and guardrails
- Speed: per‑stage timeouts (clone/install/test) target ≤30s per task.
- Reproducibility: pin commits; keep artifacts compact.
- Safety: isolate execution in Docker; internet only for git/pip installs.

### Benchmarks
- See `BENCHMARKS.md` for a growing log of model results across suites.
- Append a new row from the latest agent batch CSV (shim script calls internal module):
```bash
python -m demas.benchmarks.append --csv sandbox/agent_batch_runs/<timestamp>/summary.csv --notes "short note"
```
- Run a full sweep of all tracked models (appends rows to `BENCHMARKS.md`). Include the word `full` in notes to add to the leaderboard; all runs are also logged below:
```bash
CHUTES_API_KEY=YOUR_KEY OPENROUTER_API_KEY=YOUR_OR_KEY \
python -m demas.benchmarks.sweep \
  --seeds sandbox/swe_tasks.jsonl \
  --limit 0 \
  --jobs 12 \
  --temperature 0 \
  --notes "full suite, temp=0"
Dual‑attempt sweeps and Chutes‑only runs:
- When notes contain `full`, leaderboard rows include both `pass_rate` (attempts=1) and `pass_rate_2_attempts` (attempts=2).
- Prefer Chutes‑only sweeps when OpenRouter isn’t configured:
```bash
python -m demas.benchmarks.sweep \
  --seeds sandbox/swe_tasks.jsonl \
  --limit 0 \
  --jobs 12 \
  --notes "full suite, attempts=1 and 2, jobs=12, temp=0.2" \
  --chutes-only
```
- Refresh attempts=1 only (recomputes pass_rate for current suite):
```bash
python -m demas.benchmarks.sweep \
  --seeds sandbox/swe_tasks.jsonl \
  --limit 0 \
  --jobs 12 \
  --attempts-mode 1 \
  --notes "full suite, attempts=1 refresh, jobs=12, temp=0.2" \
  --chutes-only
```
```
 - Keep best per model on leaderboard after a full sweep:
```bash
python -m demas.benchmarks.append --normalize
```

### Benchmarks auto-append (full agent runs)
- When running a full agent suite via `swebench_batch.py` (i.e., `--agent` with `--limit 0`), a benchmark row is automatically appended to `BENCHMARKS.md` using the generated `summary.csv`.
- Use `--bench-notes "full ..."` to mark leaderboard-eligible runs and add context. Example:
```bash
CHUTES_API_KEY=YOUR_KEY python swebench_batch.py \
  --seeds sandbox/swe_tasks.jsonl \
  --agent \
  --jobs 12 \
  --bench-notes "full suite, jobs=12, temp=0.2"
```

### Next steps
- See `plan.md` for the roadmap (expand task set; agent lifts over baseline; SWE‑bench adapter; logging; config sweeps).

### Performance notes
- Parallel execution: Use `--jobs N` (agent and baseline) to reduce wall time; on a 16‑thread machine with 7 tasks, `--jobs 12–14` works well.
- Benchmarks auto‑append: Full agent runs (`--limit 0`) are persisted to `BENCHMARKS.md` automatically; add context via `--bench-notes`.

### Python virtual environment (recommended)
- Use `python3 -m venv .venv && source .venv/bin/activate` before installing requirements.
- Keep the venv active when running all commands in this README.

### Profiling
- Agent: convert logs to a CSV profile (per-tool durations):
```bash
python -m demas.benchmarks.profile --agent-run-dir sandbox/agent_batch_runs/<timestamp>
```
- Baseline: summarize per-stage durations:
```bash
python -m demas.benchmarks.profile --baseline-run-dir sandbox/batch_runs/<timestamp>
```


