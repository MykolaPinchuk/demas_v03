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

### Leaderboard (full suite only)
- Columns: `timestamp`, `model`, `pass_rate`, `p50_duration_s`, `p95_duration_s`, `notes`

<!-- MAIN_TABLE_START -->
| timestamp           | model                                      | pass_rate | p50_duration_s | p95_duration_s | notes |
|---------------------|--------------------------------------------|-----------|----------------|----------------|-------|
| 20250909_020737 | Qwen/Qwen3-Coder-30B-A3B-Instruct | 0.57 | 25.625 | 37.475 | full model sweep (no OpenAI), temp=0 |
| 20250911_002604 | Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 | 0.86 | 27.033 | 38.701 | tokens=70 full 7-task suite, jobs=12, temp=0.2 |
| 20250909_020102 | deepseek-ai/DeepSeek-V3-0324 | 0.00 | 21.419 | 24.55 | full model sweep (no OpenAI), temp=0 |
| 20250909_015718 | deepseek-ai/DeepSeek-V3.1 | 0.71 | 23.382 | 40.764 | full model sweep (no OpenAI), temp=0 |
| 20250909_015648 | moonshotai/Kimi-Dev-72B | 0.00 | 4.003 | 5.065 | full model sweep (no OpenAI), temp=0 |
| 20250910_013413 | moonshotai/Kimi-K2-Instruct-0905 | 0.71 | 28.332 | 41.137 | tokens=0 full tokenized sweep (append only > baseline), jobs=12, temp=0.2 |
| 20250909_015323 | moonshotai/Kimi-K2-Instruct-75k | 0.57 | 29.178 | 40.891 | full model sweep (no OpenAI), temp=0 |
| 20250910_010234 | openai/gpt-5-mini | 0.71 | 40.57 | 57.754 | full suite auto-append |
| 20250910_013752 | openai/gpt-oss-120b | 0.57 | 39.799 | 65.353 | tokens=0 full tokenized sweep (append only > baseline), jobs=12, temp=0.2 |
| 20250909_021738 | unsloth/gemma-3-12b-it | 0.00 | 17.667 | 20.839 | full model sweep (no OpenAI), temp=0 |
| 20250909_021357 | zai-org/GLM-4.5-Air | 0.57 | 31.814 | 46.456 | full model sweep (no OpenAI), temp=0 |
| 20250909_022525 | zai-org/GLM-4.5-FP8 | 0.86 | 26.224 | 39.613 | full suite auto-append |
| 20250911_010034 | zai-org/GLM-4.5-FP8 | 0.86 | 33.271 | 51.496 | tokens=70 full 7-task suite, attempts=2, jobs=12, temp=0.2 |
| 20250911_010322 | moonshotai/Kimi-K2-Instruct-0905 | 0.57 | 25.032 | 40.473 | tokens=50 full 7-task suite, attempts=2, jobs=12, temp=0.2 |
| 20250911_014435 | zai-org/GLM-4.5-FP8 | 0.88 | 24.101 | 26.570 | tokens=70 full 8-task suite, attempts=2, jobs=12, temp=0.2 |
| 20250911_014635 | Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 | 0.88 | 19.520 | 42.094 | tokens=80 full 8-task suite, attempts=2, jobs=12, temp=0.2 |
<!-- MAIN_TABLE_END -->

### Run log (all runs)
- Columns: `timestamp`, `model`, `pass_rate`, `p50_duration_s`, `p95_duration_s`, `notes`

<!-- LOG_TABLE_START -->
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
| 20250909_003421 | moonshotai/Kimi-K2-Instruct-75k | 1.00 | 19.607 | 15.536 | 2-task smoke, Kimi-K2-75k, temp=0.2 |
| 20250909_010004 | Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 | 0.86 | 31.878 | 42.294 | full 7-task suite, Qwen 480B FP8, jobs=12, temp=0.2 |
| 20250909_010052 | zai-org/GLM-4.5-FP8 | 0.86 | 26.284 | 38.860 | full 7-task suite, GLM-4.5-FP8, jobs=12, temp=0.2 |
| 20250909_010142 | Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 | 0.71 | 36.996 | 39.153 | full 7-task suite, Qwen 480B FP8, jobs=7, temp=0.2 |
| 20250909_014957 | moonshotai/Kimi-K2-Instruct-0905 | 0.57 | 29.445 | 41.348 | full model sweep (no OpenAI), temp=0 |
| 20250909_015323 | moonshotai/Kimi-K2-Instruct-75k | 0.57 | 29.178 | 40.891 | full model sweep (no OpenAI), temp=0 |
| 20250909_015648 | moonshotai/Kimi-Dev-72B | 0.00 | 4.003 | 5.065 | full model sweep (no OpenAI), temp=0 |
| 20250909_015718 | deepseek-ai/DeepSeek-V3.1 | 0.71 | 23.382 | 40.764 | full model sweep (no OpenAI), temp=0 |
| 20250909_020102 | deepseek-ai/DeepSeek-V3-0324 | 0.00 | 21.419 | 24.550 | full model sweep (no OpenAI), temp=0 |
| 20250909_020339 | Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 | 0.71 | 32.799 | 45.718 | full model sweep (no OpenAI), temp=0 |
| 20250909_020737 | Qwen/Qwen3-Coder-30B-A3B-Instruct | 0.57 | 25.625 | 37.475 | full model sweep (no OpenAI), temp=0 |
| 20250909_021058 | zai-org/GLM-4.5-FP8 | 0.86 | 27.403 | 30.162 | full model sweep (no OpenAI), temp=0 |
| 20250909_021357 | zai-org/GLM-4.5-Air | 0.57 | 31.814 | 46.456 | full model sweep (no OpenAI), temp=0 |
| 20250909_021738 | unsloth/gemma-3-12b-it | 0.00 | 17.667 | 20.839 | full model sweep (no OpenAI), temp=0 |
| 20250909_022023 | moonshotai/Kimi-K2-Instruct-0905 | 0.57 | 28.090 | 30.138 | full suite auto-append |
| 20250909_022023 | moonshotai/Kimi-K2-Instruct-0905 | 0.57 | 28.090 | 30.138 | full 7-task sweep (no OpenAI), jobs=12, temp=0 |
| 20250909_022100 | moonshotai/Kimi-K2-Instruct-75k | 0.57 | 34.386 | 37.415 | full suite auto-append |
| 20250909_022100 | moonshotai/Kimi-K2-Instruct-75k | 0.57 | 34.386 | 37.415 | full 7-task sweep (no OpenAI), jobs=12, temp=0 |
| 20250909_022145 | moonshotai/Kimi-Dev-72B | 0.00 | 4.407 | 6.149 | full suite auto-append |
| 20250909_022145 | moonshotai/Kimi-Dev-72B | 0.00 | 4.407 | 6.149 | full 7-task sweep (no OpenAI), jobs=12, temp=0 |
| 20250909_022151 | deepseek-ai/DeepSeek-V3.1 | 0.71 | 39.082 | 46.477 | full suite auto-append |
| 20250909_022151 | deepseek-ai/DeepSeek-V3.1 | 0.71 | 39.082 | 46.477 | full 7-task sweep (no OpenAI), jobs=12, temp=0 |
| 20250909_022308 | deepseek-ai/DeepSeek-V3-0324 | 0.00 | 21.892 | 23.900 | full suite auto-append |
| 20250909_022308 | deepseek-ai/DeepSeek-V3-0324 | 0.00 | 21.892 | 23.900 | full 7-task sweep (no OpenAI), jobs=12, temp=0 |
| 20250909_022337 | Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 | 0.86 | 31.767 | 52.043 | full suite auto-append |
| 20250909_022337 | Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 | 0.86 | 31.767 | 52.043 | full 7-task sweep (no OpenAI), jobs=12, temp=0 |
| 20250909_022430 | Qwen/Qwen3-Coder-30B-A3B-Instruct | 0.57 | 34.842 | 49.771 | full suite auto-append |
| 20250909_022430 | Qwen/Qwen3-Coder-30B-A3B-Instruct | 0.57 | 34.842 | 49.771 | full 7-task sweep (no OpenAI), jobs=12, temp=0 |
| 20250909_022525 | zai-org/GLM-4.5-FP8 | 0.86 | 26.224 | 39.613 | full suite auto-append |
| 20250909_022525 | zai-org/GLM-4.5-FP8 | 0.86 | 26.224 | 39.613 | full 7-task sweep (no OpenAI), jobs=12, temp=0 |
| 20250909_022613 | zai-org/GLM-4.5-Air | 0.57 | 41.130 | 45.711 | full suite auto-append |
| 20250909_022613 | zai-org/GLM-4.5-Air | 0.57 | 41.130 | 45.711 | full 7-task sweep (no OpenAI), jobs=12, temp=0 |
| 20250909_022700 | unsloth/gemma-3-12b-it | 0.00 | 18.126 | 19.070 | full suite auto-append |
| 20250909_022700 | unsloth/gemma-3-12b-it | 0.00 | 18.126 | 19.070 | full 7-task sweep (no OpenAI), jobs=12, temp=0 |
| 20250910_010234 | openai/gpt-5-mini | 0.71 | 40.570 | 57.754 | full suite auto-append |
| 20250910_010234 | openai/gpt-5-mini | 0.71 | 40.570 | 57.754 | full 7-task suite, OpenRouter gpt-5-mini, jobs=12, temp=0.2 |
| 20250910_010856 | openai/gpt-oss-120b | 0.57 | 46.890 | 72.806 | full suite auto-append |
| 20250910_010856 | openai/gpt-oss-120b | 0.57 | 46.890 | 72.806 | full 7-task suite, OpenRouter gpt-oss-120b, jobs=12, temp=0.2 |
| 20250910_013413 | moonshotai/Kimi-K2-Instruct-0905 | 0.71 | 28.332 | 41.137 | tokens=0 full tokenized sweep (append only > baseline), jobs=12, temp=0.2 |
| 20250910_013752 | openai/gpt-oss-120b | 0.57 | 39.799 | 65.353 | tokens=0 full tokenized sweep (append only > baseline), jobs=12, temp=0.2 |
| 20250911_002604 | Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 | 0.86 | 27.033 | 38.701 | tokens=70 full 7-task suite, jobs=12, temp=0.2 |
| 20250911_002700 | zai-org/GLM-4.5-FP8 | 0.86 | 30.104 | 41.006 | tokens=70 full 7-task suite, jobs=12, temp=0.2 |
| 20250911_002758 | moonshotai/Kimi-K2-Instruct-0905 | 0.57 | 28.725 | 45.812 | tokens=70 full 7-task suite, jobs=12, temp=0.2 |
| 20250911_010034 | zai-org/GLM-4.5-FP8 | 0.86 | 33.271 | 51.496 | tokens=70 full 7-task suite, attempts=2, jobs=12, temp=0.2 |
| 20250911_010322 | moonshotai/Kimi-K2-Instruct-0905 | 0.57 | 25.032 | 40.473 | tokens=50 full 7-task suite, attempts=2, jobs=12, temp=0.2 |
| 20250911_014435 | zai-org/GLM-4.5-FP8 | 0.88 | 24.101 | 26.570 | tokens=70 full 8-task suite, attempts=2, jobs=12, temp=0.2 |
| 20250911_014635 | Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 | 0.88 | 19.520 | 42.094 | tokens=80 full 8-task suite, attempts=2, jobs=12, temp=0.2 |
<!-- LOG_TABLE_END -->

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
| 20250906_170720 | moonshotai/Kimi-K2-Instruct-75k | 0.57 | 17.698 | 25.080 | validation sweep |
| 20250906_201923 | moonshotai/Kimi-K2-Instruct-0905 | 1.00 | 16.747 | 13.225 | 2-task smoke, Kimi-K2-0905 |
| 20250906_204513 | moonshotai/Kimi-K2-Instruct-0905 | 1.00 | 18.379 | 15.473 | post-move shim test |
| 20250907_194335 | moonshotai/Kimi-K2-Instruct-75k | 1.00 | 18.624 | 13.701 | validation sweep |
| 20250907_195415 | moonshotai/Kimi-K2-Instruct-75k | 1.00 | 21.113 | 21.113 |  |
| 20250907_200654 | moonshotai/Kimi-K2-Instruct-0905 | 0.57 | 32.338 | 47.708 | full 7-task sweep, temp=0 |
| 20250907_201036 | moonshotai/Kimi-K2-Instruct-75k | 0.57 | 32.363 | 42.521 | full 7-task sweep, temp=0 |
| 20250907_201416 | moonshotai/Kimi-Dev-72B | 0.00 | 3.280 | 3.393 | full 7-task sweep, temp=0 |
| 20250907_201438 | deepseek-ai/DeepSeek-V3.1 | 0.57 | 34.737 | 47.735 | full 7-task sweep, temp=0 |
| 20250907_201853 | deepseek-ai/DeepSeek-V3-0324 | 0.00 | 21.610 | 25.435 | full 7-task sweep, temp=0 |
| 20250907_202121 | openai/gpt-oss-120b | 0.00 | 13.327 | 13.687 | full 7-task sweep, temp=0 |
| 20250907_202252 | openai/gpt-oss-20b | 0.00 | 9.900 | 14.364 | full 7-task sweep, temp=0 |
| 20250907_202410 | Qwen/Qwen3-Coder-480B-A35B-Instruct-FP8 | 0.86 | 46.330 | 60.000 | full 7-task sweep, temp=0 |
| 20250907_202938 | Qwen/Qwen3-Coder-30B-A3B-Instruct | 0.71 | 23.524 | 33.578 | full 7-task sweep, temp=0 |
| 20250907_203247 | zai-org/GLM-4.5-FP8 | 0.86 | 24.169 | 27.281 | full 7-task sweep, temp=0 |
