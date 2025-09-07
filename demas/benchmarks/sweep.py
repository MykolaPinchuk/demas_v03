import os
import sys
import json
import time
import subprocess
from datetime import datetime
from typing import List

from demas.core.models import TRACKED_MODELS, DEFAULT_TEMPERATURE, DEFAULT_MAX_TURNS
from demas.core.io import load_seed_tasks
from demas.core.summaries import write_agent_csv
from demas.benchmarks.append import parse_csv, derive_timestamp, append_row
from demas.core import config as _cfg  # triggers local credentials loading


def run_agent_batch(seeds: str, limit: int, model: str, *, temperature: float) -> str:
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join("sandbox", "agent_batch_runs", ts)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "logs"), exist_ok=True)
    out_path = os.path.join(out_dir, "results.jsonl")
    csv_path = os.path.join(out_dir, "summary.csv")

    tasks = load_seed_tasks(seeds)
    if limit > 0:
        tasks = tasks[:limit]

    with open(out_path, "w", encoding="utf-8") as outf:
        for task in tasks:
            env = os.environ.copy()
            env.setdefault("SWE_IMAGE", "swebench-lite:py3.10")
            env["TARGET_REPO"] = task.get("repo", "")
            env["TARGET_REF"] = task.get("ref", "")
            env["PYTEST_K"] = task.get("pytest_k", "")
            env["MODEL_NAME"] = model
            env["MODEL_TEMPERATURE"] = str(temperature)
            env["MAX_TURNS"] = str(DEFAULT_MAX_TURNS)
            # per-task timeouts
            to = task.get("timeouts", {}) or {}
            if isinstance(to, dict):
                if to.get("clone"):
                    env["TIMEOUT_CLONE"] = str(int(to["clone"]))
                if to.get("install"):
                    env["TIMEOUT_INSTALL"] = str(int(to["install"]))
                if to.get("test"):
                    env["TIMEOUT_TEST"] = str(int(to["test"]))
            env["RUN_BASE_DIR"] = out_dir
            env["TASK_ID"] = task.get("task_id", "")

            t0 = time.time()
            p = subprocess.run([sys.executable, "-m", "demas.swe.oneagent"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
            dt = time.time() - t0
            out = p.stdout or ""
            # tail extraction
            tail = ""
            for ln in out.splitlines()[::-1]:
                s = (ln or "").strip()
                if not s:
                    continue
                if ("passed" in s) or ("failed" in s) or ("error" in s):
                    tail = s
                    break
            status = "pass" if (" passed" in tail and " failed" not in tail and " error" not in tail) else "fail"
            rec = {
                "task_id": task.get("task_id", ""),
                "repo": task.get("repo", ""),
                "ref": task.get("ref", ""),
                "pytest_k": task.get("pytest_k", ""),
                "status": status,
                "duration_s": round(dt, 3),
                "tail": tail,
                "model": model,
                "temperature": temperature,
                "max_turns": DEFAULT_MAX_TURNS,
            }
            outf.write(json.dumps(rec) + "\n")
            outf.flush()
            print(f"{task.get('task_id','')} -> {tail} ({status})")

    # write CSV
    rows = []
    with open(out_path, "r", encoding="utf-8") as inf:
        for line in inf:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    write_agent_csv(rows, csv_path)
    print(f"Wrote results: {out_path}\nWrote CSV: {csv_path}")
    return csv_path


def main(argv: List[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Run a full benchmark sweep across all tracked models")
    ap.add_argument("--seeds", default="sandbox/swe_tasks.jsonl", help="Seed tasks JSONL (default: sandbox/swe_tasks.jsonl)")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of tasks (0 = all)")
    ap.add_argument("--models", nargs="*", default=None, help="Override model list; default uses TRACKED_MODELS")
    ap.add_argument("--notes", default="", help="Notes appended to BENCHMARKS.md rows")
    ap.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE, help="Sampling temperature for all models (default from registry)")
    args = ap.parse_args(argv)

    if not os.environ.get("CHUTES_API_KEY"):
        print("Error: CHUTES_API_KEY not set in env.", file=sys.stderr)
        return 2

    models = args.models if args.models else TRACKED_MODELS
    print(f"Sweeping {len(models)} models...")
    for m in models:
        print(f"\n=== Model: {m} ===")
        csv_path = run_agent_batch(args.seeds, args.limit, m, temperature=args.temperature)
        info = parse_csv(csv_path)
        ts = derive_timestamp(csv_path)
        append_row("BENCHMARKS.md", ts, info.get("model", m), info.get("pass_rate", ""), info.get("p50", ""), info.get("p95", ""), args.notes)
        print(f"Appended BENCHMARKS row for {m} @ {ts}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


