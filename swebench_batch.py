#!/usr/bin/env python3
import os
import sys
import json
import time
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from demas.core.io import load_seed_tasks
from demas.core.summaries import write_baseline_csv, write_agent_csv
from demas.core import config as _cfg  # triggers local credentials loading


ROOT = os.path.abspath(os.path.dirname(__file__))
SANDBOX = os.path.join(ROOT, "sandbox")
RUNS_DIR = os.path.join(SANDBOX, "runs")
SEEDS_DEFAULT = os.path.join(SANDBOX, "seed_tasks.jsonl")


def list_run_subdirs() -> List[str]:
    if not os.path.isdir(RUNS_DIR):
        return []
    names = [d for d in os.listdir(RUNS_DIR) if os.path.isdir(os.path.join(RUNS_DIR, d))]
    names.sort()
    return names


def run_baseline_for_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke swebench_baseline.py with the given task_id and read the latest result.json."""
    before = set(list_run_subdirs())
    task_id = task.get("task_id", "")

    cmd = [sys.executable, "-m", "demas.swe.baseline", "--task-id", task_id]
    # Optional: override repo/ref/pytest_k from seed in case fields are missing in baseline
    if task.get("repo"):
        cmd += ["--repo", task["repo"]]
    if task.get("ref"):
        cmd += ["--ref", task["ref"]]
    if task.get("pytest_k"):
        cmd += ["--pytest-k", task["pytest_k"]]

    subprocess.run(cmd, check=False)

    # Find new run dir
    after = set(list_run_subdirs())
    new_dirs = sorted(list(after - before))
    if not new_dirs:
        return {"task_id": task_id, "error": "no_run_dir_detected"}
    latest = new_dirs[-1]
    result_path = os.path.join(RUNS_DIR, latest, "result.json")
    try:
        with open(result_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return {"task_id": task_id, "error": f"result_read_failed: {e}"}


def run_agent_for_task(task: Dict[str, Any], *, out_dir: str, model: str, temperature: float, max_turns: int) -> Dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("SWE_IMAGE", "swebench-lite:py3.10")
    env["TARGET_REPO"] = task.get("repo", "")
    env["TARGET_REF"] = task.get("ref", "")
    env["PYTEST_K"] = task.get("pytest_k", "")
    # Model configuration
    if model:
        env["MODEL_NAME"] = model
    if temperature is not None:
        env["MODEL_TEMPERATURE"] = str(temperature)
    if max_turns:
        env["MAX_TURNS"] = str(int(max_turns))
    # Per-task timeouts
    to = task.get("timeouts", {}) or {}
    if isinstance(to, dict):
        if to.get("clone"):
            env["TIMEOUT_CLONE"] = str(int(to["clone"]))
        if to.get("install"):
            env["TIMEOUT_INSTALL"] = str(int(to["install"]))
        if to.get("test"):
            env["TIMEOUT_TEST"] = str(int(to["test"]))
    # Logging config
    env["RUN_BASE_DIR"] = out_dir
    env["TASK_ID"] = task.get("task_id", "")

    t0 = time.time()
    p = subprocess.run(
        [sys.executable, "-m", "demas.swe.oneagent"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    dt = time.time() - t0
    out = p.stdout or ""
    # Heuristic: last pytest tail appears as e.g. "X passed in Ys" on a line by itself
    tail = ""
    model_used = model or ""
    for ln in out.splitlines()[::-1]:
        ln = ln.strip()
        if not ln:
            continue
        if "passed" in ln or "failed" in ln or "error" in ln:
            tail = ln
            break
    # Try to detect model used from preflight output if available
    for ln in out.splitlines():
        if ln.strip().startswith("[preflight] Using model:"):
            try:
                model_used = ln.split(":", 1)[1].strip()
            except Exception:
                pass
    status = "pass" if " passed" in tail and " failed" not in tail and " error" not in tail else "fail"
    return {
        "task_id": task.get("task_id", ""),
        "repo": task.get("repo", ""),
        "ref": task.get("ref", ""),
        "pytest_k": task.get("pytest_k", ""),
        "status": status,
        "duration_s": round(dt, 3),
        "tail": tail,
        "model": model_used,
        "temperature": temperature,
        "max_turns": max_turns,
    }


def _run_single_task(task: Dict[str, Any], *, agent: bool, out_dir: str, model: str, temperature: float, max_turns: int) -> Tuple[Dict[str, Any], str]:
    if agent:
        res = run_agent_for_task(task, out_dir=out_dir, model=model, temperature=temperature, max_turns=max_turns)
    else:
        # Ensure unique timestamp per baseline task to avoid collisions
        os.environ["RUN_TS"] = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        res = run_baseline_for_task(task)
    msg = f"{task.get('task_id','')} -> {res.get('tail','')} ({res.get('status','?')})"
    return res, msg


def main(argv: List[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Batch runner for SWE seeds (baseline or agent mode)")
    parser.add_argument("--seeds", default=SEEDS_DEFAULT, help="Path to seed JSONL file (default: sandbox/seed_tasks.jsonl)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tasks to run (0 = all)")
    parser.add_argument("--agent", action="store_true", help="Use agent mode instead of baseline (requires CHUTES_API_KEY)")
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", ""), help="Agent model name (env MODEL_NAME default)")
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("MODEL_TEMPERATURE", "0.2")), help="Sampling temperature (env MODEL_TEMPERATURE default)")
    parser.add_argument("--max-turns", dest="max_turns", type=int, default=int(os.environ.get("MAX_TURNS", "10")), help="Maximum agent turns (env MAX_TURNS default)")
    parser.add_argument("--jobs", type=int, default=1, help="Parallel jobs (agent mode only). Default: 1")
    args = parser.parse_args(argv)

    tasks = load_seed_tasks(args.seeds)
    if args.limit > 0:
        tasks = tasks[: args.limit]

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    if args.agent:
        if not os.environ.get("CHUTES_API_KEY"):
            print("Error: CHUTES_API_KEY not set in env.", file=sys.stderr)
            return 2
        out_dir = os.path.join(SANDBOX, "agent_batch_runs", ts)
    else:
        out_dir = os.path.join(SANDBOX, "batch_runs", ts)
    os.makedirs(out_dir, exist_ok=True)
    if args.agent:
        os.makedirs(os.path.join(out_dir, "logs"), exist_ok=True)
    out_path = os.path.join(out_dir, "results.jsonl")
    csv_path = os.path.join(out_dir, "summary.csv")

    t0 = time.time()
    # Write results incrementally with a lock to support parallel workers
    write_lock = threading.Lock()
    with open(out_path, "w", encoding="utf-8") as outf:
        if max(1, args.jobs) > 1:
            # Parallel runs (agent or baseline)
            workers = max(1, args.jobs)
            with ThreadPoolExecutor(max_workers=workers) as ex:
                future_to_task = {
                    ex.submit(_run_single_task, task, agent=args.agent, out_dir=out_dir, model=args.model, temperature=args.temperature, max_turns=args.max_turns): task
                    for task in tasks
                }
                for fut in as_completed(future_to_task):
                    try:
                        res, msg = fut.result()
                    except Exception as e:
                        res = {"task_id": future_to_task[fut].get("task_id", ""), "error": f"worker_failed: {e}"}
                        msg = f"{res.get('task_id','')} -> (error) ({e})"
                    with write_lock:
                        outf.write(json.dumps(res) + "\n")
                        outf.flush()
                    print(msg)
        else:
            # Sequential (baseline or single-job agent)
            for task in tasks:
                res, msg = _run_single_task(task, agent=args.agent, out_dir=out_dir, model=args.model, temperature=args.temperature, max_turns=args.max_turns)
                outf.write(json.dumps(res) + "\n")
                outf.flush()
                print(msg)

    # CSV summary via shared helper
    try:
        rows = []
        with open(out_path, "r", encoding="utf-8") as inf:
            for line in inf:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        if args.agent:
            write_agent_csv(rows, csv_path)
        else:
            write_baseline_csv(rows, csv_path)
        print(f"Wrote results: {out_path}\nWrote CSV: {csv_path}")
    except Exception as e:
        print(f"(CSV summary failed): {e}")

    print(f"Elapsed seconds: {time.time() - t0:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


