#!/usr/bin/env python3
"""Shim script delegating to demas.benchmarks.append without changing CLI."""
import os
import sys
import argparse
from demas.benchmarks.append import parse_csv, derive_timestamp, append_row


ROOT = os.path.abspath(os.path.dirname(__file__))
BM_PATH = os.path.join(ROOT, "BENCHMARKS.md")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Append a benchmark summary row to BENCHMARKS.md from an agent batch CSV")
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


