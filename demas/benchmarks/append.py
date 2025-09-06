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
    for row in rows:
        if len(row) >= 7 and row[0] and row[0] != "task_id" and row[0] != "pass_rate":
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
    return os.path.basename(os.path.dirname(csv_path))


def append_row(md_path: str, ts: str, model: str, pass_rate: str, p50: str, p95: str, notes: str):
    line = f"| {ts} | {model} | {pass_rate or 'NA'} | {p50 or 'NA'} | {p95 or 'NA'} | {notes or ''} |\n"
    with open(md_path, "a", encoding="utf-8") as f:
        f.write(line)


