## Model Benchmarks (growing log)

Purpose: Track model performance across our evaluation suites. This file will grow as we add new tasks, suites, and models.

### Current suite
- Suite: Agentic run on 2 SWE-style tasks from `sandbox/swe_tasks.jsonl`
- Tasks: `swe_demo_numpy_financial` (pinned commit), `swe_demo_pluggy`
- Runner: `swebench_agent_batch.py`
- Docker image: `swebench-lite:py3.10`
- Timeouts (default): clone 5s, install 20s, test 5s (per-task overrides allowed)
- Agent config (typical): `--temperature 0.2`, `--max-turns 5`
- Outputs: `sandbox/agent_batch_runs/<timestamp>/{results.jsonl, summary.csv, logs/}`

### How to run a benchmark (per model)
```bash
CHUTES_API_KEY=YOUR_KEY \
python swebench_agent_batch.py \
  --seeds sandbox/swe_tasks.jsonl \
  --limit 2 \
  --model <MODEL_NAME> \
  --temperature 0.2 \
  --max-turns 5
```

Then open the newest `sandbox/agent_batch_runs/<ts>/summary.csv` and record:
- pass_rate
- p50_duration_s
- p95_duration_s
- notes (if errors/instability)

### Results (latest entries)
- Columns: `timestamp`, `model`, `pass_rate`, `p50_duration_s`, `p95_duration_s`, `notes`

| timestamp           | model                                      | pass_rate | p50_duration_s | p95_duration_s | notes |
|---------------------|--------------------------------------------|-----------|----------------|----------------|-------|
| 20250905_022404     | deepseek-ai/DeepSeek-V3-0324               | 1.00      | 26.287         | 22.001         | stable |
| 20250905_022240     | moonshotai/Kimi-K2-Instruct-75k            | 1.00      | 20.041         | 15.160         | fastest stable among originals |
| 20250905_021650     | Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8    | 1.00      | 21.939         | 17.382         | stable |
| 20250905_021030     | zai-org/GLM-4.5-FP8                        | 1.00      | 24.236         | 19.699         | stable |
| 20250905_021137     | deepseek-ai/DeepSeek-V3.1                  | 1.00      | 27.730         | 24.050         | stable |
| 20250905_021451     | zai-org/GLM-4.5-Air                        | 1.00      | 47.294         | 34.064         | slower |
| 20250905_021744     | Qwen/Qwen3-Coder-30B-A3B-Instruct          | 0.50      | 15.486         | 14.534         | unstable (failed 1/2) |
| 20250905_022030     | unsloth/gemma-3-12b-it                     | 0.00      | 17.477         | 17.199         | both failed (API error) |
| 20250905_022331     | openai/gpt-oss-120b                        | 0.00      | 11.326         | 11.000         | both failed (API error) |
| 20250905_022509     | openai/gpt-oss-20b                         | 0.00      | 13.338         | 12.630         | both failed (API error) |
| 20250905_022117     | moonshotai/Kimi-Dev-72B                    | 0.00      | 3.450          | 3.138          | both failed (runtime error) |

Notes:
- Times vary slightly run-to-run; prefer the most recent timestamp per model for comparisons.
- pass_rate reflects strict “pass” detection from pytest tail; anything else is treated as fail.
- JSONL logs for each task are in `sandbox/agent_batch_runs/<ts>/logs/<task_id>.jsonl` with redaction and 8KB truncation for large outputs.

### Adding new suites or tasks
- When adding tasks (e.g., expand `sandbox/swe_tasks.jsonl` to 5–10 items), create a new subsection here specifying:
  - Suite name and task list
  - Runner flags (temperature, max_turns, timeouts if customized)
  - A results table with the same columns
- Keep older sections for historical reference. Avoid editing past results; add new rows with new timestamps.


| 20250905_025710 | moonshotai/Kimi-K2-Instruct-75k | 0.43 | 25.419 | 36.048 | 7-task suite, Kimi-K2, PYTHONPATH+auto-install enabled |
| 20250905_030112 | Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 | 0.43 | 31.508 | 35.820 | 7-task suite, Qwen 480B FP8, PYTHONPATH+auto-install |
| 20250905_031235 | Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 | 1.00 | 26.839 | 26.839 | post-refactor smoke (3 tasks), Qwen 480B FP8 |
| 20250905_031529 | Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 | 0.57 | 29.990 | 38.298 | 7-task suite, Qwen 480B FP8, post-refactor |
| 20250906_010859 | moonshotai/Kimi-K2-Instruct-0905 | 0.57 | 25.596 | 31.745 | 7-task suite, Kimi-K2-0905 |
