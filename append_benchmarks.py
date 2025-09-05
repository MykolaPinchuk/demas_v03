#!/usr/bin/env python3
"""
Append a benchmark summary row to BENCHMARKS.md from a batch CSV.

Usage:
  python append_benchmarks.py --csv sandbox/agent_batch_runs/<ts>/summary.csv [--notes "..."]

It extracts:
- timestamp: derived from parent directory name (<ts>)
- model, temperature, max_turns: from first data row
- pass_rate, p50_duration_s, p95_duration_s: from CSV footer

Appends a Markdown table row under the "Results (latest entries)" section of BENCHMARKS.md.
Safe to run multiple times; it just appends a new row at the end.
"""
import os
import sys
import csv
import argparse


ROOT = os.path.abspath(os.path.dirname(__file__))
BM_PATH = os.path.join(ROOT, "BENCHMARKS.md")


def parse_csv(path: str):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        r = csv.reader(f)
        for row in r:
            rows.append(row)
    # Extract footer values
    pass_rate = ""
    p50 = ""
    p95 = ""
    model = ""
    temperature = ""
    max_turns = ""
    # First data row typically at index 1 (after header and maybe blank line)
    for row in rows:
        if len(row) >= 7 and row[0] and row[0] != "task_id" and row[0] != "pass_rate":
            # task row
            if not model and len(row) >= 7:
                model = row[4]
                temperature = row[5]
                max_turns = row[6]
        if len(row) >= 2:
            if row[0] == "pass_rate":
                pass_rate = row[1]
            elif row[0] == "p50_duration_s":
                p50 = row[1]
            elif row[0] == "p95_duration_s":
                p95 = row[1]
    return {
        "model": model,
        "temperature": temperature,
        "max_turns": max_turns,
        "pass_rate": pass_rate,
        "p50": p50,
        "p95": p95,
    }


def derive_timestamp(csv_path: str) -> str:
    # Expect .../agent_batch_runs/<ts>/summary.csv
    parent = os.path.basename(os.path.dirname(csv_path))
    return parent


def append_row(md_path: str, ts: str, model: str, pass_rate: str, p50: str, p95: str, notes: str):
    line = f"| {ts} | {model} | {pass_rate or 'NA'} | {p50 or 'NA'} | {p95 or 'NA'} | {notes or ''} |\n"
    with open(md_path, "a", encoding="utf-8") as f:
        f.write(line)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to agent batch summary.csv")
    ap.add_argument("--notes", default="", help="Optional notes for the row")
    args = ap.parse_args(argv)

    csv_path = os.path.abspath(args.csv)
    if not os.path.isfile(csv_path):
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 2

    meta = parse_csv(csv_path)
    ts = derive_timestamp(csv_path)
    append_row(
        BM_PATH,
        ts,
        meta.get("model", ""),
        meta.get("pass_rate", ""),
        meta.get("p50", ""),
        meta.get("p95", ""),
        args.notes,
    )
    print(f"Appended benchmark row for {ts} -> {meta.get('model','')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


