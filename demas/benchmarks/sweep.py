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


def run_agent_batch(seeds: str, limit: int, model: str, *, temperature: float, jobs: int) -> str:
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


def main(argv: List[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Run a full benchmark sweep across all tracked models")
    ap.add_argument("--seeds", default="sandbox/swe_tasks.jsonl", help="Seed tasks JSONL (default: sandbox/swe_tasks.jsonl)")
    ap.add_argument("--limit", type=int, default=0, help="Limit number of tasks (0 = all)")
    ap.add_argument("--models", nargs="*", default=None, help="Override model list; default uses TRACKED_MODELS")
    ap.add_argument("--notes", default="", help="Notes appended to BENCHMARKS.md rows (include 'full' to mark leaderboard)")
    ap.add_argument("--temperature", type=float, default=DEFAULT_TEMPERATURE, help="Sampling temperature for all models (default from registry)")
    ap.add_argument("--jobs", type=int, default=12, help="Parallel jobs per model for task runs (agent mode)")
    args = ap.parse_args(argv)

    if not os.environ.get("CHUTES_API_KEY"):
        print("Error: CHUTES_API_KEY not set in env.", file=sys.stderr)
        return 2

    models = args.models if args.models else TRACKED_MODELS
    print(f"Sweeping {len(models)} models...")
    for m in models:
        print(f"\n=== Model: {m} ===")
        csv_path = run_agent_batch(args.seeds, args.limit, m, temperature=args.temperature, jobs=args.jobs)
        info = parse_csv(csv_path)
        ts = derive_timestamp(csv_path)
        append_row("BENCHMARKS.md", ts, info.get("model", m), info.get("pass_rate", ""), info.get("p50", ""), info.get("p95", ""), args.notes)
        print(f"Appended BENCHMARKS row for {m} @ {ts}")
    # Normalize leaderboard to best per model if notes indicate full suite
    try:
        if "full" in (args.notes or '').lower():
            from demas.benchmarks.append import normalize_leaderboard
            normalize_leaderboard("BENCHMARKS.md")
            print("Normalized leaderboard to best row per model.")
    except Exception as e:
        print(f"(Normalization failed): {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


