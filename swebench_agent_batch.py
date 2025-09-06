#!/usr/bin/env python3
import os
import re
import sys
import json
import time
import subprocess
from datetime import datetime
from typing import List, Dict, Any

from demas.core.io import load_seed_tasks
from demas.core.summaries import write_agent_csv


ROOT = os.path.abspath(os.path.dirname(__file__))
SANDBOX = os.path.join(ROOT, "sandbox")
SEEDS_DEFAULT = os.path.join(SANDBOX, "seed_tasks.jsonl")

TAIL_RE = re.compile(r"(\d+\s+(passed|failed|errors?|error|skipped|deselected).*)")


def run_agent_for_task(task: Dict[str, Any], *, out_dir: str, model: str, temperature: float, max_turns: int) -> Dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("SWE_IMAGE", "swebench-lite:py3.10")
    env["TARGET_REPO"] = task.get("repo", "")
    env["TARGET_REF"] = task.get("ref", "")
    env["PYTEST_K"] = task.get("pytest_k", "")
    # Model configuration (CLI overrides env by passing explicit values)
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
        [sys.executable, os.path.join(ROOT, "team_swebench_oneagent.py")],
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


def main(argv: List[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Agent batch runner for SWE seeds")
    parser.add_argument("--seeds", default=SEEDS_DEFAULT, help="Path to seed JSONL file (default: sandbox/seed_tasks.jsonl)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tasks to run (0 = all)")
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", ""), help="Agent model name (env MODEL_NAME default)")
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("MODEL_TEMPERATURE", "0.2")), help="Sampling temperature (env MODEL_TEMPERATURE default)")
    parser.add_argument("--max-turns", dest="max_turns", type=int, default=int(os.environ.get("MAX_TURNS", "10")), help="Maximum agent turns (env MAX_TURNS default)")
    args = parser.parse_args(argv)

    if not os.environ.get("CHUTES_API_KEY"):
        print("Error: CHUTES_API_KEY not set in env.", file=sys.stderr)
        return 2

    tasks = load_seed_tasks(args.seeds)
    if args.limit > 0:
        tasks = tasks[: args.limit]

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(SANDBOX, "agent_batch_runs", ts)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "logs"), exist_ok=True)
    out_path = os.path.join(out_dir, "results.jsonl")
    csv_path = os.path.join(out_dir, "summary.csv")

    with open(out_path, "w", encoding="utf-8") as outf:
        for task in tasks:
            res = run_agent_for_task(task, out_dir=out_dir, model=args.model, temperature=args.temperature, max_turns=args.max_turns)
            outf.write(json.dumps(res) + "\n")
            outf.flush()
            print(f"{task.get('task_id','')} -> {res.get('tail','')} ({res.get('status','?')})")

    # CSV summary via shared helper
    try:
        rows = []
        with open(out_path, "r", encoding="utf-8") as inf:
            for line in inf:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        write_agent_csv(rows, csv_path)
        print(f"Wrote results: {out_path}\nWrote CSV: {csv_path}")
    except Exception as e:
        print(f"(CSV summary failed): {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


