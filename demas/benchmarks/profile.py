#!/usr/bin/env python3
"""
Profiling utilities for DEMAS runs.

Agent mode:
- Parse sandbox/agent_batch_runs/<ts>/logs/*.jsonl and extract per-tool durations
  (clone, install, pytest passes, pip install, patch) and total run time.
- Write a CSV profile next to the run dir.

Baseline mode:
- Parse sandbox/batch_runs/<ts>/results.jsonl (with per-stage timings) and
  write a CSV summary.
"""

import os
import json
import glob
from typing import Dict, Any, List, Tuple


def _parse_agent_log(path: str) -> Dict[str, Any]:
    """Return durations (seconds) for key phases in a single agent log."""
    # We rely on paired records: assistant CALL <tool> and tool result for <tool>.
    # Use the string timestamps, which are ISO8601Z; compare as floats via ordering index.
    import datetime as _dt

    def _to_ts(s: str) -> float:
        try:
            return _dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0

    with open(path, "r", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    task_id = ""
    model = ""
    run_start = None
    run_end = None

    # Track first CALL ts and matching tool result ts
    call_ts: Dict[str, float] = {}
    durations: Dict[str, float] = {}

    def _close(tool_name: str, end_ts: float):
        st = call_ts.pop(tool_name, None)
        if st is not None and end_ts >= st:
            durations[tool_name] = round(end_ts - st, 3)

    for r in rows:
        ts = _to_ts(r.get("timestamp", ""))
        role = r.get("role", "")
        content = r.get("content", "") or ""
        tn = r.get("tool_name")
        task_id = r.get("task_id", task_id)
        model = r.get("model", model)
        if role == "system" and content == "run_started":
            run_start = ts
        # Record last ts as run end heuristic
        if ts:
            run_end = ts
        # Track calls and completions by tool_name
        if role == "assistant" and tn in ("swe_clone", "swe_install", "swe_pytest", "swe_pytest_auto", "swe_pytest_full", "swe_pip_install", "swe_apply_patch_text"):
            call_ts[tn] = ts
        if role == "tool" and tn in call_ts:
            _close(tn, ts)

    total = round((run_end - run_start), 3) if (run_start and run_end and run_end >= run_start) else 0.0

    return {
        "task_id": task_id or os.path.splitext(os.path.basename(path))[0],
        "model": model,
        "clone_s": durations.get("swe_clone", 0.0),
        "install_s": durations.get("swe_install", 0.0),
        "pytest_auto_s": durations.get("swe_pytest_auto", 0.0),
        "pytest_full_s": durations.get("swe_pytest_full", 0.0),
        "pytest_s": durations.get("swe_pytest", 0.0),
        "pip_install_s": durations.get("swe_pip_install", 0.0),
        "patch_s": durations.get("swe_apply_patch_text", 0.0),
        "total_s": total,
    }


def profile_agent_run(run_dir: str) -> str:
    """Profile an agent batch run dir and write CSV; return CSV path."""
    logs_dir = os.path.join(run_dir, "logs")
    out_csv = os.path.join(run_dir, "profile.csv")
    files = sorted(glob.glob(os.path.join(logs_dir, "*.jsonl")))
    rows = [_parse_agent_log(p) for p in files]
    import csv
    with open(out_csv, "w", newline="", encoding="utf-8") as cf:
        w = csv.writer(cf)
        w.writerow(["task_id", "model", "clone_s", "install_s", "pytest_auto_s", "pytest_full_s", "pytest_s", "pip_install_s", "patch_s", "total_s"])
        for r in rows:
            w.writerow([r["task_id"], r["model"], r["clone_s"], r["install_s"], r["pytest_auto_s"], r["pytest_full_s"], r["pytest_s"], r["pip_install_s"], r["patch_s"], r["total_s"]])
    return out_csv


def profile_baseline_run(run_dir: str) -> str:
    """Profile a baseline batch run dir and write CSV; return CSV path."""
    src = os.path.join(run_dir, "results.jsonl")
    out_csv = os.path.join(run_dir, "profile.csv")
    rows: List[Dict[str, Any]] = []
    with open(src, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    import csv
    with open(out_csv, "w", newline="", encoding="utf-8") as cf:
        w = csv.writer(cf)
        w.writerow(["task_id", "clone_s", "install_s", "test_s", "total_s"])
        for r in rows:
            w.writerow([
                r.get("task_id", ""),
                r.get("duration_clone_s", 0.0),
                r.get("duration_install_s", 0.0),
                r.get("duration_test_s", 0.0),
                r.get("duration_s", 0.0),
            ])
    return out_csv


def _latest(dir_path: str) -> str:
    subs = [os.path.join(dir_path, d) for d in os.listdir(dir_path) if os.path.isdir(os.path.join(dir_path, d))]
    subs.sort()
    return subs[-1] if subs else dir_path


def main(argv: List[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Profile DEMAS runs and write CSV summaries")
    ap.add_argument("--agent-run-dir", default="", help="Path to sandbox/agent_batch_runs/<ts>")
    ap.add_argument("--baseline-run-dir", default="", help="Path to sandbox/batch_runs/<ts>")
    args = ap.parse_args(argv)

    if args.agent_run_dir:
        run_dir = args.agent_run_dir
    else:
        agent_root = os.path.join("sandbox", "agent_batch_runs")
        run_dir = _latest(agent_root)
    if os.path.isdir(os.path.join(run_dir, "logs")):
        csv_path = profile_agent_run(run_dir)
        print(f"Agent profile -> {csv_path}")

    if args.baseline_run_dir:
        base_dir = args.baseline_run_dir
    else:
        base_root = os.path.join("sandbox", "batch_runs")
        base_dir = _latest(base_root)
    if os.path.isfile(os.path.join(base_dir, "results.jsonl")):
        csv_path = profile_baseline_run(base_dir)
        print(f"Baseline profile -> {csv_path}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))


