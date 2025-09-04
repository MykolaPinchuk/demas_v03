#!/usr/bin/env python3
import os
import re
import sys
import json
import time
import subprocess
from datetime import datetime
from typing import List, Dict, Any


ROOT = os.path.abspath(os.path.dirname(__file__))
SANDBOX = os.path.join(ROOT, "sandbox")
SEEDS_DEFAULT = os.path.join(SANDBOX, "seed_tasks.jsonl")

TAIL_RE = re.compile(r"(\d+\s+(passed|failed|errors?|error|skipped|deselected).*)")


def load_seed_tasks(path: str) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            tasks.append(rec)
    return tasks


def run_agent_for_task(task: Dict[str, Any]) -> Dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("SWE_IMAGE", "swebench-lite:py3.10")
    env["TARGET_REPO"] = task.get("repo", "")
    env["TARGET_REF"] = task.get("ref", "")
    env["PYTEST_K"] = task.get("pytest_k", "")

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
    for ln in out.splitlines()[::-1]:
        ln = ln.strip()
        if not ln:
            continue
        if "passed" in ln or "failed" in ln or "error" in ln:
            tail = ln
            break
    status = "pass" if " passed" in tail and " failed" not in tail and " error" not in tail else ("fail" if tail else "unknown")
    return {
        "task_id": task.get("task_id", ""),
        "repo": task.get("repo", ""),
        "ref": task.get("ref", ""),
        "pytest_k": task.get("pytest_k", ""),
        "status": status,
        "duration_s": round(dt, 3),
        "tail": tail,
    }


def main(argv: List[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Agent batch runner for SWE seeds")
    parser.add_argument("--seeds", default=SEEDS_DEFAULT, help="Path to seed JSONL file")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tasks (0 = all)")
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
    out_path = os.path.join(out_dir, "results.jsonl")
    csv_path = os.path.join(out_dir, "summary.csv")

    with open(out_path, "w", encoding="utf-8") as outf:
        for task in tasks:
            res = run_agent_for_task(task)
            outf.write(json.dumps(res) + "\n")
            outf.flush()
            print(f"{task.get('task_id','')} -> {res.get('tail','')} ({res.get('status','?')})")

    # CSV summary
    try:
        import csv
        rows = []
        with open(out_path, "r", encoding="utf-8") as inf:
            for line in inf:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        pass_count = sum(1 for r in rows if r.get("status") == "pass")
        total = len(rows)
        pass_rate = (pass_count / total) if total else 0.0
        durations = [r.get("duration_s", 0.0) for r in rows if isinstance(r.get("duration_s"), (int, float))]

        with open(csv_path, "w", newline="", encoding="utf-8") as cf:
            w = csv.writer(cf)
            w.writerow(["task_id", "status", "duration_s", "tail"])  # header
            for r in rows:
                w.writerow([
                    r.get("task_id", ""),
                    r.get("status", ""),
                    r.get("duration_s", ""),
                    r.get("tail", "").replace("\n", " ")[:200],
                ])
            w.writerow([])
            w.writerow(["pass_rate", f"{pass_rate:.2f}"])
        print(f"Wrote results: {out_path}\nWrote CSV: {csv_path}")
    except Exception as e:
        print(f"(CSV summary failed): {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


