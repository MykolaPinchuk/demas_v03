#!/usr/bin/env python3
import os
import sys
import json
import time
import subprocess
from datetime import datetime
from typing import List, Dict, Any


ROOT = os.path.abspath(os.path.dirname(__file__))
SANDBOX = os.path.join(ROOT, "sandbox")
RUNS_DIR = os.path.join(SANDBOX, "runs")
SEEDS_DEFAULT = os.path.join(SANDBOX, "seed_tasks.jsonl")


def load_seed_tasks(path: str) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    seen_ids = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = rec.get("task_id")
            if tid and tid in seen_ids:
                continue
            if tid:
                seen_ids.add(tid)
            tasks.append(rec)
    return tasks


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

    cmd = [sys.executable, os.path.join(ROOT, "swebench_baseline.py"), "--task-id", task_id]
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


def main(argv: List[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Batch runner for SWE seeds (baseline mode)")
    parser.add_argument("--seeds", default=SEEDS_DEFAULT, help="Path to seed JSONL file")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tasks (0 = all)")
    args = parser.parse_args(argv)

    tasks = load_seed_tasks(args.seeds)
    if args.limit > 0:
        tasks = tasks[: args.limit]

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(SANDBOX, "batch_runs", ts)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "results.jsonl")
    csv_path = os.path.join(out_dir, "summary.csv")

    t0 = time.time()
    with open(out_path, "w", encoding="utf-8") as outf:
        for task in tasks:
            res = run_baseline_for_task(task)
            outf.write(json.dumps(res) + "\n")
            outf.flush()
            print(f"{task.get('task_id','')} -> {res.get('tail','')} ({res.get('status','?')})")

    # Also write a CSV summary (task_id, status, duration_s, tail)
    try:
        import csv  # stdlib
        rows = []
        with open(out_path, "r", encoding="utf-8") as inf:
            for line in inf:
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rows.append(r)
        # Compute simple stats
        durations = [r.get("duration_s", 0.0) for r in rows if isinstance(r.get("duration_s"), (int, float))]
        pass_count = sum(1 for r in rows if r.get("status") == "pass")
        total = len(rows)
        pass_rate = (pass_count / total) if total else 0.0
        # Write CSV
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
            if durations:
                import statistics as stats
                p50 = stats.median(durations)
                p95 = sorted(durations)[max(0, int(0.95 * (len(durations) - 1)))]
                w.writerow(["p50_duration_s", f"{p50:.3f}"])
                w.writerow(["p95_duration_s", f"{p95:.3f}"])
        print(f"Wrote CSV: {csv_path}")
    except Exception as e:
        print(f"(CSV summary failed): {e}")

    print(f"Wrote results: {out_path}")
    print(f"Elapsed seconds: {time.time() - t0:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


