from typing import List, Dict, Any


def write_baseline_csv(rows: List[Dict[str, Any]], csv_path: str) -> None:
    import csv
    durations = [r.get("duration_s", 0.0) for r in rows if isinstance(r.get("duration_s"), (int, float))]
    pass_count = sum(1 for r in rows if r.get("status") == "pass")
    total = len(rows)
    pass_rate = (pass_count / total) if total else 0.0
    with open(csv_path, "w", newline="", encoding="utf-8") as cf:
        w = csv.writer(cf)
        w.writerow(["task_id", "status", "duration_s", "tail"])  # header
        for r in rows:
            w.writerow([
                r.get("task_id", ""),
                r.get("status", ""),
                r.get("duration_s", ""),
                (r.get("tail", "") or "").replace("\n", " ")[:200],
            ])
        w.writerow([])
        w.writerow(["pass_rate", f"{pass_rate:.2f}"])
        if durations:
            import statistics as stats
            p50 = stats.median(durations)
            p95 = sorted(durations)[max(0, int(0.95 * (len(durations) - 1)))]
            w.writerow(["p50_duration_s", f"{p50:.3f}"])
            w.writerow(["p95_duration_s", f"{p95:.3f}"])


def write_agent_csv(rows: List[Dict[str, Any]], csv_path: str) -> None:
    import csv
    pass_count = sum(1 for r in rows if r.get("status") == "pass")
    total = len(rows)
    pass_rate = (pass_count / total) if total else 0.0
    durations = [r.get("duration_s", 0.0) for r in rows if isinstance(r.get("duration_s"), (int, float))]
    with open(csv_path, "w", newline="", encoding="utf-8") as cf:
        w = csv.writer(cf)
        w.writerow(["task_id", "status", "duration_s", "tail", "model", "temperature", "max_turns"])  # header
        for r in rows:
            w.writerow([
                r.get("task_id", ""),
                r.get("status", ""),
                r.get("duration_s", ""),
                (r.get("tail", "") or "").replace("\n", " ")[:200],
                r.get("model", ""),
                r.get("temperature", ""),
                r.get("max_turns", ""),
            ])
        w.writerow([])
        w.writerow(["pass_rate", f"{pass_rate:.2f}"])
        if durations:
            import statistics as stats
            p50 = stats.median(durations)
            p95 = sorted(durations)[max(0, int(0.95 * (len(durations) - 1)))]
            w.writerow(["p50_duration_s", f"{p50:.3f}"])
            w.writerow(["p95_duration_s", f"{p95:.3f}"])


