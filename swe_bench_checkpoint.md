SWE-Bench Checkpoint
## Revised Fast-Iteration Plan (P0 → P3)

- **Constraints**: Python-only; internet only for `git clone` and `pip install`; provider Chutes; per-run target ≤ 30s; prioritize speed and simplicity.

- **Iteration 0: Baseline + Fast Image**
  - Build a Docker image `swebench-lite:py3.10` preinstalling `pytest`, `numpy`, `pandas`.
  - Single runner script: clone → install → pytest with strict stage timeouts (clone 5s, install 20s, tests 5s).
  - Emit compact JSON result and pytest tail into `sandbox/runs/<ts>/`.

- **Iteration 1: Stable Seeds**
  - Add a local `seed_tasks.jsonl` with a few tiny numpy/pandas repos/refs and optional `-k` filters.
  - CLI can run via direct args or `--task-id` from the seeds file.

- **Iteration 2: Patch Application**
  - Accept a unified diff; apply inside the same container prior to running tests; record before/after pytest tails.
  - Guardrails: reject oversized/complex diffs to maintain speed.

- **Iteration 3: One-Agent Integration**
  - Expose tools `swe_clone`, `swe_install`, `swe_apply_patch`, `swe_pytest` with same timeouts.
  - Terminate on pytest tail patterns or max turns; capture model usage if available.

- **Cross-cutting**
  - Deterministic outputs (JSON result schema: `{task_id, repo, ref, pytest_k, status, duration_s, tail}`).
  - Minimal logs and artifacts to keep I/O small; per-stage timeouts enforce the 30s cap.
  - Keep container offline except for `pip install`.
1. High-Level Plan

We are building an evaluation harness for SWE-bench problems (software engineering tasks from real GitHub issues/PRs).
The goal is to:

Run a coding agent (via AutoGen + Chutes provider) to attempt a SWE-bench task.

Place the task inside a controlled Docker container (Python 3.10 image).

Let the agent:

Clone the target repo at the correct commit (from SWE-bench dataset).

Apply patches / edits.

Run pytest to validate correctness.

Collect results: pass/fail, runtime, tokens used, etc.

Scale from one simple problem → multiple pandas/numpy problems → the full SWE-bench subset.

2. Context

Environment:

Python 3.10 base image (swebench-lite:py3.10).

AutoGen AssistantAgent team configured with Docker execution tool (docker_sh).

Chutes API used to call external LLMs (moonshotai/Kimi-K2-Instruct-75k validated).

Dataset:

SWE-bench dataset contains GitHub repos, commits, and tests.

Starting focus: pandas/numpy problems (faster to run, smaller runtime footprint).

Validation logic:

A minimal script runs three steps in Docker:

Clone repo

Install dependencies

Run pytest (possibly narrowed with -k <keyword> for speed).

3. What We Have Built So Far

Docker Image (swebench-lite:py3.10):

Based on python:3.10 with git preinstalled.

Mount point /workspace.

Repo Validation Scripts:

repo_validate_docker.py and later versions successfully cloned & ran tests against pytest repo.

Output confirmed runs like 1 passed, 1 deselected in 0.05s.

Issues encountered:

Missing pytest inside container → fixed by explicit pip install pytest.

Pyproject minversion warnings handled by ensuring pytest>=8.4.

Autogen Agents:

Multi-agent setup (Planner, Coder, Tester).

Verified they can:

Write code into sandbox/.

Run pytest inside Docker.

Detect success and terminate.

Observed behavior:

Early runs looped on termination conditions (TERMINATE repeated).

Simplified to single-agent (Runner) with strict instructions → stable runs.

Repo validation on external projects (pytest) works end-to-end.

4. What We Are About To Do Next

Integrate SWE-bench dataset:

Start with one single pandas/numpy problem (fast, lightweight).

Mount problem into Docker container.

Have agent apply solution patch + rerun tests.

Extend scripts:

Add loader to fetch SWE-bench task metadata (repo URL, commit, test command).

Adapt current repo_validate_docker_vN.py into swebench_run_one.py.

Validate pipeline:

Confirm agent can solve at least one SWE-bench instance in full cycle:

Checkout correct commit.

Apply patch (if instructed).

Run tests → observe green.

Next scaling step:

Once single task works, generalize to multiple tasks with config.

Collect metrics (success rate, runtime, tokens).

5. Notes for Next Agent

Docker caching: Image swebench-lite:py3.10 is already built — reuse it.

Repo location: All SWE-bench tasks clone into /workspace/project.

Execution tools: Use swe_clone, swe_install, swe_pytest.

Termination: Do NOT emit “TERMINATE” unless you intend to stop — otherwise infinite loops may occur.


## General guidelines for agent:
- Do not overengineer.
- Follow iterative development. Do any thing at a time, validate that that it works, then progress.




Starting point:

Take repo_validate_docker_v5.py as baseline.

Swap out hard-coded repo/args with SWE-bench metadata loader.

First test target:

Pick one pandas/numpy SWE-bench case (small runtime footprint).