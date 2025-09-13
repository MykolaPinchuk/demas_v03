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


def run_agent_batch(seeds: str, limit: int, model: str, *, temperature: float, jobs: int, attempts: int = 1) -> str:
    """Delegate to swebench_batch.py to leverage its parallel --jobs implementation.
    Returns the summary.csv path parsed from stdout.
    """
    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "swebench_batch.py"),
        "--seeds", seeds,
        "--limit", str(limit),
        "--agent",
        "--model", model,
        "--temperature", str(temperature),
        "--jobs", str(max(1, jobs)),
        "--attempts", str(max(1, attempts)),
        "--no-auto-append",
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = p.stdout or ""
    csv_path = ""
    for ln in out.splitlines():
        if ln.startswith("Wrote CSV:"):
            csv_path = ln.split(":", 1)[1].strip()
    if not csv_path:
        raise RuntimeError(f"Could not determine CSV path from swebench_batch output:\n{out}")
    return csv_path


def run_baseline_batch(seeds: str, limit: int, *, jobs: int) -> str:
    cmd = [
        sys.executable,
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "swebench_batch.py"),
        "--seeds", seeds,
        "--limit", str(limit),
        "--jobs", str(max(1, jobs)),
    ]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    out = p.stdout or ""
    csv_path = ""
    for ln in out.splitlines():
        if ln.startswith("Wrote CSV:"):
            csv_path = ln.split(":", 1)[1].strip()
    if not csv_path:
        raise RuntimeError(f"Could not determine baseline CSV path from swebench_batch output:\n{out}")
    return csv_path


def main(argv: List[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Run a full benchmark sweep across all tracked models")
    ap.add_argument("--seeds", default="sandbox/swe_tasks.jsonl", help="Seed tasks JSONL (default: sandbox/swe_tasks.jsonl)")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of tasks (0 = all)")
    ap.add_argument("--models", nargs="*", default=None, help="Override model list; default uses TRACKED_MODELS")
    ap.add_argument("--notes", default="", help="Notes appended to BENCHMARKS.md rows (include 'full' to mark leaderboard)")
    ap.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE, help="Sampling temperature for all models (default from registry)")
    ap.add_argument("--jobs", type=int, default=12, help="Parallel jobs per model for task runs (agent mode)")
    ap.add_argument("--chutes-only", action="store_true", help="Evaluate only models routed via Chutes (exclude openai/* which go to OpenRouter)")
    ap.add_argument("--attempts-mode", choices=["1","2","both"], default="both", help="Whether to run attempts=1, attempts=2, or both (default: both)")
    args = ap.parse_args(argv)

    if not os.environ.get("CHUTES_API_KEY"):
        print("Error: CHUTES_API_KEY not set in env.", file=sys.stderr)
        return 2

    # Compute baseline pass_rate once
    print("Running baseline to compute pass_rate for comparison...")
    base_csv = run_baseline_batch(args.seeds, args.limit, jobs=args.jobs)
    # Extract baseline pass_rate
    baseline_pass_rate = 0.0
    try:
        with open(base_csv, "r", encoding="utf-8") as f:
            import csv as _csv
            for row in _csv.reader(f):
                if len(row) >= 2 and row[0] == "pass_rate":
                    baseline_pass_rate = float(row[1])
                    break
    except Exception:
        pass
    print(f"Baseline pass_rate: {baseline_pass_rate:.2f}")

    models = args.models if args.models else TRACKED_MODELS
    if args.chutes_only:
        models = [m for m in models if not str(m).lower().startswith("openai/")]
    print(f"Sweeping {len(models)} models...")
    for m in models:
        print(f"\n=== Model: {m} ===")
        pr1 = pr2 = p50 = p95 = ""
        ts = ""
        info_model = m
        if args.attempts_mode in ("1","both"):
            csv1 = run_agent_batch(args.seeds, args.limit, m, temperature=args.temperature, jobs=args.jobs, attempts=1)
            info1 = parse_csv(csv1)
            ts1 = derive_timestamp(csv1)
            pr1 = info1.get("pass_rate", "")
            info_model = info1.get("model", m)
            ts = ts1
        if args.attempts_mode in ("2","both"):
            csv2 = run_agent_batch(args.seeds, args.limit, m, temperature=args.temperature, jobs=args.jobs, attempts=2)
            info2 = parse_csv(csv2)
            ts2 = derive_timestamp(csv2)
            pr2 = info2.get("pass_rate", "")
            p50 = info2.get("p50", "")
            p95 = info2.get("p95", "")
            info_model = info2.get("model", info_model)
            ts = ts2 or ts
        # Append depending on notes/baseline
        try:
            agent_pass_rate = float(pr1 or 0.0)
        except Exception:
            agent_pass_rate = 0.0
        if "full" in (args.notes or '').lower():
            append_row("BENCHMARKS.md", ts, info_model, pr1, p50, p95, args.notes, (info2.get("tokens_total", "") if args.attempts_mode in ("2","both") else ""), pr2)
            print(f"Appended BENCHMARKS row for {m} @ {ts} (full-suite run; attempts-mode={args.attempts_mode})")
        else:
            if agent_pass_rate > baseline_pass_rate:
                append_row("BENCHMARKS.md", ts, info_model, pr1, p50, p95, args.notes, (info2.get("tokens_total", "") if args.attempts_mode in ("2","both") else ""), pr2)
                print(f"Appended BENCHMARKS row for {m} @ {ts} (agent {agent_pass_rate:.2f} > baseline {baseline_pass_rate:.2f}; attempts-mode={args.attempts_mode})")
            else:
                print(f"Skipped append for {m}: agent {agent_pass_rate:.2f} <= baseline {baseline_pass_rate:.2f}")
    # Normalize leaderboard to best per model if notes indicate full suite
    try:
        if "full" in (args.notes or '').lower():
            from demas.benchmarks.append import normalize_leaderboard
            # Prefer rows from the latest dual-attempt runs when available
            normalize_leaderboard("BENCHMARKS.md", suite_marker="attempts=1 and 2")
            print("Normalized leaderboard to best row per model.")
    except Exception as e:
        print(f"(Normalization failed): {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


