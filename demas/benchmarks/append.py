import os
import csv


def parse_csv(path: str):
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        r = csv.reader(f)
        for row in r:
            rows.append(row)
    pass_rate = ""
    p50 = ""
    p95 = ""
    model = ""
    temperature = ""
    max_turns = ""
    tokens_total = 0
    for row in rows:
        if len(row) >= 7 and row[0] and row[0] != "task_id" and row[0] != "pass_rate":
            if not model and len(row) >= 7:
                model = row[4]
                temperature = row[5]
                max_turns = row[6]
            # sum tokens_total if present (new columns at indices -1)
            try:
                if row and row[-1] and row[0] != "task_id":
                    tokens_total += int(row[-1])
            except Exception:
                pass
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
        "tokens_total": str(tokens_total),
    }


def derive_timestamp(csv_path: str) -> str:
    return os.path.basename(os.path.dirname(csv_path))


def append_row(md_path: str, ts: str, model: str, pass_rate: str, p50: str, p95: str, notes: str, tokens: str = ""):
    note_tokens = f"tokens={tokens} " if tokens else ""
    line = f"| {ts} | {model} | {pass_rate or 'NA'} | {p50 or 'NA'} | {p95 or 'NA'} | {note_tokens}{notes or ''} |\n"
    with open(md_path, "r+", encoding="utf-8") as f:
        content = f.read()
        # Always append to the run log table
        if "<!-- LOG_TABLE_END -->" in content:
            content = content.replace("<!-- LOG_TABLE_END -->", line + "<!-- LOG_TABLE_END -->")
        else:
            content = content + "\n" + line
        # Only add to leaderboard if this is a full suite (notes contains 'full' and limit not present)
        is_full = "full" in (notes or "").lower()
        if is_full and "<!-- MAIN_TABLE_END -->" in content:
            content = content.replace("<!-- MAIN_TABLE_END -->", line + "<!-- MAIN_TABLE_END -->")
        f.seek(0)
        f.write(content)
        f.truncate()


def _parse_table_rows(section: str):
    rows = []
    for line in section.splitlines():
        line = line.strip()
        if not line or line.startswith("|") is False:
            continue
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 6 or parts[0] == "timestamp":
            continue
        try:
            rows.append({
                "timestamp": parts[0],
                "model": parts[1],
                "pass_rate": float(parts[2]) if parts[2] else 0.0,
                "p50": float(parts[3]) if parts[3] else 0.0,
                "p95": float(parts[4]) if parts[4] else 0.0,
                "notes": parts[5],
            })
        except Exception:
            continue
    return rows


def normalize_leaderboard(md_path: str) -> None:
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()
    # Extract log section
    try:
        log_start = content.index("<!-- LOG_TABLE_START -->")
        log_end = content.index("<!-- LOG_TABLE_END -->")
    except ValueError:
        return
    log_section = content[log_start:log_end]
    all_rows = _parse_table_rows(log_section)
    # Consider only rows whose notes contain 'full'
    full_rows = [r for r in all_rows if "full" in (r.get("notes", "").lower())]
    # Select best per model: max pass_rate, tie-break min p50
    best_by_model = {}
    for r in full_rows:
        m = r["model"]
        prev = best_by_model.get(m)
        if prev is None:
            best_by_model[m] = r
        else:
            if (r["pass_rate"] > prev["pass_rate"]) or (
                r["pass_rate"] == prev["pass_rate"] and r["p50"] < prev["p50"]
            ):
                best_by_model[m] = r
    # Build new main table
    header = (
        "| timestamp           | model                                      | pass_rate | p50_duration_s | p95_duration_s | notes |\n"
        "|---------------------|--------------------------------------------|-----------|----------------|----------------|-------|\n"
    )
    rows_md = []
    for model in sorted(best_by_model.keys()):
        r = best_by_model[model]
        rows_md.append(
            f"| {r['timestamp']} | {r['model']} | {r['pass_rate']:.2f} | {r['p50']} | {r['p95']} | {r['notes']} |\n"
        )
    new_main = "<!-- MAIN_TABLE_START -->\n" + header + "".join(rows_md) + "<!-- MAIN_TABLE_END -->"
    # Replace main table section
    try:
        main_start = content.index("<!-- MAIN_TABLE_START -->")
        main_end = content.index("<!-- MAIN_TABLE_END -->") + len("<!-- MAIN_TABLE_END -->")
        updated = content[:main_start] + new_main + content[main_end:]
    except ValueError:
        # If missing, just append
        updated = content + "\n\n" + new_main
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(updated)


def main(argv: list[str]) -> int:
    import argparse
    p = argparse.ArgumentParser(description="Append a benchmark summary row to BENCHMARKS.md")
    p.add_argument("--csv", help="Path to agent batch summary.csv")
    p.add_argument("--notes", default="", help="Short notes to include in the row")
    p.add_argument("--md", default="BENCHMARKS.md", help="Markdown file to append to (default: BENCHMARKS.md)")
    p.add_argument("--normalize", action="store_true", help="Normalize leaderboard to best row per model (based on LOG table 'full' rows)")
    args = p.parse_args(argv)
    if args.normalize:
        normalize_leaderboard(args.md)
        print("Normalized leaderboard to best row per model.")
        return 0
    if not args.csv:
        p.error("--csv is required unless --normalize is set")
    info = parse_csv(args.csv)
    ts = derive_timestamp(args.csv)
    append_row(args.md, ts, info.get("model", ""), info.get("pass_rate", ""), info.get("p50", ""), info.get("p95", ""), args.notes)
    print(f"Appended row for {ts} -> {args.md}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv[1:]))

