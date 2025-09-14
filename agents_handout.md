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


### Evaluation principles (read this before running sweeps)
- Objective: distinguish good agents/models from weak ones clearly and reproducibly.
- Two key levers to keep evaluations meaningful:
  1) Keep baseline pass_rate low. Avoid including trivially passing tasks in the scoring suite. Use strict caps, light `-k` selectors, and curated failing commits that require a minimal patch.
  2) Maximize spread between best and worst models. Prefer tasks that strong models can solve reliably within caps, while weak models struggle.
- Harness guidelines:
  - Run a quick pre-test before install; early-exit on pass. Do not waste budget on installs when not needed.
  - Use small `-k` filters so tests fit in 5–8s. If a repo can’t fit, exclude it from the scoring suite.
  - Pin failing commits when possible (via `demas.adapters.swebench`) so success depends on a surgical code change, not infra luck.
  - Append all runs to `BENCHMARKS.md` but interpret leaderboards with baseline context.
  - Keep internet usage minimal: only git/pip; avoid heavy downloads that won’t finish within caps.


### Where to pick up (current eval state and next steps)

Current state (as of latest runs):
- Scoring suite trimmed to 6 tasks in `sandbox/swe_tasks.jsonl` (easy-pass repos removed). Two curated local tasks were added but are not yet scoring-ready.
- Strict caps remain (clone=5s, install=30s). Test caps per task tuned to 5–10s using `pytest_k` when needed.
- Baseline pass_rate ≈ 0.17 on the 6-task suite; top Chutes models ≈ 0.67 (attempts=1). Spread is acceptable; baseline is low.
- Runners/harness:
  - Baseline runs a pre-test before install and is resilient to install failures.
  - Agent runs a pre-test before install and early-exits on pass; sweep appends all runs to `BENCHMARKS.md`.

Suite details (scoring):
- Present tasks include: numpy-financial (pinned), click (`-k help`), packaging (`-k version`), sortedcontainers (small `-k`), attrs (`-k version`), jmespath (`-k lexer`).
- Two local curated fast-fail tasks exist under `sandbox/local_repos/{demo_add,demo_upper}` and are listed in `swe_tasks.jsonl`, but they currently fail at install. These should be treated as future scoring candidates.

What’s left to do (priority):
1) Make local curated tasks scoring-ready:
   - For repos under `/workspace/local_repos/...`, skip install and run tests directly from source by exporting `PYTHONPATH=$PWD:$PWD/src:$PYTHONPATH` for pre-test and test phases.
   - Update baseline (and optionally agent) to detect local paths and bypass editable installs for these tasks.
   - Verify baseline runs show pre-test tails for `demo_add` and `demo_upper` and that agents can patch them within caps.
2) Restore an 8-task scoring suite:
   - Either enable the two curated local tasks (preferred) or swap in two curated failing commits via `demas.adapters.swebench` that run <8s and require a minimal one-diff fix.
3) Re-run attempts=1 for top models to validate spread:
   - Chutes: `Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8`, `zai-org/GLM-4.5-FP8`, `deepseek-ai/DeepSeek-V3.1`.
   - OpenRouter (optional): `openai/gpt-oss-120b`, `openai/gpt-5-mini`.
   - Ensure `BENCHMARKS.md` captures runs; add notes describing suite version and caps.
4) (Optional) attempts=2:
   - If needed for additional separation, run attempts=2 and normalize the leaderboard to the best per model (prefer dual-attempt rows when meaningful).

Quick commands (reference):
```bash
# Build image (if needed)
docker build -f Dockerfile.swe -t swebench-lite:py3.10 .

# Baseline full suite (sequential for clarity)
source .venv/bin/activate
python swebench_batch.py --seeds sandbox/swe_tasks.jsonl --limit 0 --jobs 1

# Two-model sweep (attempts=1) with notes
python -m demas.benchmarks.sweep \
  --seeds sandbox/swe_tasks.jsonl \
  --limit 0 \
  --jobs 12 \
  --temperature 0.2 \
  --attempts-mode 1 \
  --notes "scoring suite vX; attempts=1; strict caps"
  --models Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 zai-org/GLM-4.5-FP8
```

Guardrails to preserve signal:
- Keep baseline low: avoid adding trivially passing tasks to the scoring set.
- Keep caps strict and use `-k` to fit tests into 5–8s; document any per-task exceptions.
- When changing the suite, note the suite version and rationale in the sweep `--notes` and in `BENCHMARKS.md` so results remain comparable.

