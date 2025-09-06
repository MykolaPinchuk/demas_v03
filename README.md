## DEMAS – Fast Harness for Agentic Coding (SWE-bench style)

This repository is the first step toward a Dynamic Evolutionary Multi‑Agent System (DEMAS) for agentic coding. It provides a fast, reproducible harness to run and evaluate code changes inside Docker, with both a baseline (no AI) mode and an AI agent mode (via Chutes).

Docs map:
- High‑level vision and motivation: `vision.md`
- Roadmap, constraints, and detailed next steps: `plan.md`

### Repo structure (key files)
- Docker and runners (root scripts = stable CLIs; internal logic under `demas/`)
  - `Dockerfile.swe`: Python 3.10 + git + preinstalled `pytest`, `numpy`, `pandas` for speed.
  - `swebench_run_one.py`: run a single SWE‑style task (baseline or `--agent`).
  - `swebench_baseline.py`: baseline execution (uses internal helpers).
  - `swebench_batch.py`: run multiple tasks and write JSONL + CSV summaries (uses internal helpers).
  - `swebench_agent_batch.py`: run the agent across tasks and summarize (uses internal helpers).
  - `team_swebench_oneagent.py`: one‑agent runner (also exposed as `demas.swe.oneagent`).
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
- Python 3.10+ on host: `pip install -r requirements.txt` (for the agent scripts).
- Chutes API key for agent mode: set `CHUTES_API_KEY`.

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
CHUTES_API_KEY=YOUR_KEY python swebench_agent_batch.py --seeds sandbox/swe_tasks.jsonl
```
Agent batch outputs:
- `sandbox/agent_batch_runs/<timestamp>/{results.jsonl, summary.csv}`

### Task format
Local JSONL schema used by both baseline and agent:
```json
{"task_id":"id","repo":"https://github.com/org/repo","ref":"<commit-or-branch>","pytest_k":"","patch_b64":"","timeouts":{"clone":5,"install":20,"test":5}}
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
python append_benchmarks.py --csv sandbox/agent_batch_runs/<timestamp>/summary.csv --notes "short note"
```

### Next steps
- See `plan.md` for the roadmap (expand task set; agent lifts over baseline; SWE‑bench adapter; logging; config sweeps).


