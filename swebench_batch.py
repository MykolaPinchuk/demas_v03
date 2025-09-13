#!/usr/bin/env python3
import os
import sys
import json
import time
import subprocess
from datetime import datetime
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from demas.core.io import load_seed_tasks
from demas.core.summaries import write_baseline_csv, write_agent_csv
from demas.core import config as _cfg  # triggers local credentials loading


ROOT = os.path.abspath(os.path.dirname(__file__))
SANDBOX = os.path.join(ROOT, "sandbox")
RUNS_DIR = os.path.join(SANDBOX, "runs")
SEEDS_DEFAULT = os.path.join(SANDBOX, "seed_tasks.jsonl")


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

    cmd = [sys.executable, "-m", "demas.swe.baseline", "--task-id", task_id]
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


def _build_attempt_hint(log_path: str, size_cap_bytes: int = 2048) -> str:
    """Construct a concise hint from the prior attempt's agent log JSONL."""
    tail = ""
    diag = ""
    missing = ""
    patch = ""
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                tool = rec.get("tool_name")
                role = rec.get("role", "")
                content = rec.get("content") or ""
                result = rec.get("tool_result") or ""
                if tool in ("swe_pytest", "swe_pytest_auto") and role == "tool":
                    tail = result
                if tool == "swe_pytest_full" and role == "tool":
                    diag = result
                if role == "assistant" and "Detected missing module:" in content:
                    missing = content
                if tool == "swe_apply_patch_text" and role == "tool":
                    patch = result
    except Exception:
        pass
    parts = []
    if tail:
        parts.append(f"last_tail: {tail}")
    if missing:
        parts.append(missing)
    if patch:
        parts.append(f"patch_result: {patch}")
    if diag:
        parts.append(f"diag: {diag}")
    hint = " \n".join(parts)
    if len(hint.encode("utf-8")) > size_cap_bytes:
        enc = hint.encode("utf-8")[:size_cap_bytes]
        try:
            hint = enc.decode("utf-8", errors="ignore") + "...<truncated>"
        except Exception:
            hint = hint[:512] + "...<truncated>"
    return hint


def run_agent_for_task(task: Dict[str, Any], *, out_dir: str, model: str, temperature: float, max_turns: int, attempts: int, attempt_cap_s: int) -> Dict[str, Any]:
    env = os.environ.copy()
    env.setdefault("SWE_IMAGE", "swebench-lite:py3.10")
    env["TARGET_REPO"] = task.get("repo", "")
    env["TARGET_REF"] = task.get("ref", "")
    env["PYTEST_K"] = task.get("pytest_k", "")
    # Model configuration
    if model:
        env["MODEL_NAME"] = model
    if temperature is not None:
        env["MODEL_TEMPERATURE"] = str(temperature)
    if max_turns:
        env["MAX_TURNS"] = str(int(max_turns))
    # Per-task timeouts
    to = task.get("timeouts", {}) or {}
    if isinstance(to, dict):
        if to.get("clone"):
            env["TIMEOUT_CLONE"] = str(int(to["clone"]))
        if to.get("install"):
            env["TIMEOUT_INSTALL"] = str(int(to["install"]))
        if to.get("test"):
            env["TIMEOUT_TEST"] = str(int(to["test"]))
    # Attempts loop with per-attempt cap and hint propagation
    attempts_n = max(1, int(attempts))
    model_used = model or ""
    start_overall = time.time()
    last_hint = ""
    last_tail = ""
    def _extract_tail_from_log(log_path: str) -> str:
        """Read the agent log and return the last pytest tail emitted by swe_pytest/_auto.

        This avoids relying on stdout of the agent process, which may contain
        wrapper objects (e.g., FunctionExecutionResult) rather than raw tails.
        """
        try:
            last_tail = ""
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    rec = json.loads(line)
                    if rec.get("role") == "tool" and rec.get("tool_name") in ("swe_pytest", "swe_pytest_auto"):
                        tr = rec.get("tool_result") or ""
                        if isinstance(tr, str) and tr.strip():
                            last_tail = tr.strip()
            return last_tail
        except Exception:
            return ""

    for k in range(1, attempts_n + 1):
        env_k = env.copy()
        attempt_dir = os.path.join(out_dir, f"attempt_{k}")
        os.makedirs(os.path.join(attempt_dir, "logs"), exist_ok=True)
        env_k["RUN_BASE_DIR"] = attempt_dir
        env_k["TASK_ID"] = task.get("task_id", "")
        if last_hint:
            env_k["ATTEMPT_HINT"] = last_hint
        t0 = time.time()
        try:
            p = subprocess.run(
                [sys.executable, "-m", "demas.swe.oneagent"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env=env_k,
                timeout=max(1, int(attempt_cap_s)),
            )
            out = p.stdout or ""
        except subprocess.TimeoutExpired as e:
            # e.stdout may be bytes depending on the platform/config; coerce safely
            _s = e.stdout
            if isinstance(_s, bytes):
                try:
                    _s = _s.decode("utf-8", errors="ignore")
                except Exception:
                    _s = ""
            out = ( _s or "" ) + "\n(timeout)"
        dt_k = time.time() - t0
        # Determine tail: prefer reading from the JSONL logs (reliable), fallback to stdout scan
        log_path = os.path.join(attempt_dir, "logs", f"{task.get('task_id','')}.jsonl")
        tail = _extract_tail_from_log(log_path)
        if not tail:
            for ln in out.splitlines()[::-1]:
                ln = ln.strip()
                if not ln:
                    continue
                if "passed" in ln or "failed" in ln or "error" in ln or "no tests ran" in ln:
                    tail = ln
                    break
        last_tail = tail or last_tail
        # Model detection (first available)
        if not model_used:
            for ln in out.splitlines():
                if ln.strip().startswith("[preflight] Using model:"):
                    try:
                        model_used = ln.split(":", 1)[1].strip()
                    except Exception:
                        pass
                    break
        passed = (" passed" in last_tail and " failed" not in last_tail and " error" not in last_tail)
        if passed:
            total_dt = time.time() - start_overall
            return {
                "task_id": task.get("task_id", ""),
                "repo": task.get("repo", ""),
                "ref": task.get("ref", ""),
                "pytest_k": task.get("pytest_k", ""),
                "status": "pass",
                "duration_s": round(total_dt, 3),
                "tail": last_tail,
                "model": model_used,
                "temperature": temperature,
                "max_turns": max_turns,
            }
        # Build hint for next attempt
        last_hint = _build_attempt_hint(log_path, size_cap_bytes=2048)
    # All attempts failed
    total_dt = time.time() - start_overall
    return {
        "task_id": task.get("task_id", ""),
        "repo": task.get("repo", ""),
        "ref": task.get("ref", ""),
        "pytest_k": task.get("pytest_k", ""),
        "status": "fail",
        "duration_s": round(total_dt, 3),
        "tail": last_tail,
        "model": model_used,
        "temperature": temperature,
        "max_turns": max_turns,
    }


def _run_single_task(task: Dict[str, Any], *, agent: bool, out_dir: str, model: str, temperature: float, max_turns: int, attempts: int, attempt_cap_s: int) -> Tuple[Dict[str, Any], str]:
    if agent:
        res = run_agent_for_task(task, out_dir=out_dir, model=model, temperature=temperature, max_turns=max_turns, attempts=attempts, attempt_cap_s=attempt_cap_s)
    else:
        # Ensure unique timestamp per baseline task to avoid collisions
        os.environ["RUN_TS"] = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        res = run_baseline_for_task(task)
    msg = f"{task.get('task_id','')} -> {res.get('tail','')} ({res.get('status','?')})"
    return res, msg


def main(argv: List[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Batch runner for SWE seeds (baseline or agent mode)")
    parser.add_argument("--seeds", default=SEEDS_DEFAULT, help="Path to seed JSONL file (default: sandbox/seed_tasks.jsonl)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of tasks to run (0 = all)")
    parser.add_argument("--agent", action="store_true", help="Use agent mode instead of baseline (requires CHUTES_API_KEY)")
    parser.add_argument("--model", default=os.environ.get("MODEL_NAME", ""), help="Agent model name (env MODEL_NAME default)")
    parser.add_argument("--temperature", type=float, default=float(os.environ.get("MODEL_TEMPERATURE", "0.2")), help="Sampling temperature (env MODEL_TEMPERATURE default)")
    parser.add_argument("--max-turns", dest="max_turns", type=int, default=int(os.environ.get("MAX_TURNS", "10")), help="Maximum agent turns (env MAX_TURNS default)")
    parser.add_argument("--jobs", type=int, default=0, help="Parallel jobs for both modes (0 or negative = auto; default: auto)")
    parser.add_argument("--attempts", type=int, default=1, help="Agent attempts per task (fresh runs). Default 1")
    parser.add_argument("--attempt-cap-s", type=int, default=60, help="Per-attempt wall-clock cap in seconds (default: 60)")
    parser.add_argument("--bench-notes", default=os.environ.get("BENCH_NOTES", ""), help="Optional notes to include when auto-appending full-suite agent results to BENCHMARKS.md (include 'full' to appear on leaderboard)")
    parser.add_argument("--no-auto-append", action="store_true", help="Disable auto-append to BENCHMARKS.md even for full agent runs")
    args = parser.parse_args(argv)

    tasks = load_seed_tasks(args.seeds)
    if args.limit > 0:
        tasks = tasks[: args.limit]

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # Determine default parallelism if not specified (>0).
    # Default to max(12, cpu_count - 2) to avoid regressions in concurrency.
    import os as _os
    if args.jobs <= 0:
        cpu = _os.cpu_count() or 4
        auto_jobs = max(12, max(1, cpu - 2))
        args.jobs = auto_jobs
        try:
            print(f"[parallel] Auto-selected jobs={args.jobs} (cpu={cpu})")
        except Exception:
            pass
    if args.agent:
        if not os.environ.get("CHUTES_API_KEY"):
            print("Error: CHUTES_API_KEY not set in env.", file=sys.stderr)
            return 2
        out_dir = os.path.join(SANDBOX, "agent_batch_runs", ts)
    else:
        out_dir = os.path.join(SANDBOX, "batch_runs", ts)
    os.makedirs(out_dir, exist_ok=True)
    if args.agent:
        os.makedirs(os.path.join(out_dir, "logs"), exist_ok=True)
    out_path = os.path.join(out_dir, "results.jsonl")
    csv_path = os.path.join(out_dir, "summary.csv")

    t0 = time.time()
    # Write results incrementally with a lock to support parallel workers
    write_lock = threading.Lock()
    with open(out_path, "w", encoding="utf-8") as outf:
        if max(1, args.jobs) > 1:
            # Parallel runs (agent or baseline)
            workers = max(1, args.jobs)
            with ThreadPoolExecutor(max_workers=workers) as ex:
                future_to_task = {
                    ex.submit(_run_single_task, task, agent=args.agent, out_dir=out_dir, model=args.model, temperature=args.temperature, max_turns=args.max_turns, attempts=args.attempts, attempt_cap_s=args.attempt_cap_s): task
                    for task in tasks
                }
                for fut in as_completed(future_to_task):
                    try:
                        res, msg = fut.result()
                    except Exception as e:
                        res = {"task_id": future_to_task[fut].get("task_id", ""), "error": f"worker_failed: {e}"}
                        msg = f"{res.get('task_id','')} -> (error) ({e})"
                    with write_lock:
                        outf.write(json.dumps(res) + "\n")
                        outf.flush()
                    print(msg)
        else:
            # Sequential (baseline or single-job agent)
            for task in tasks:
                res, msg = _run_single_task(task, agent=args.agent, out_dir=out_dir, model=args.model, temperature=args.temperature, max_turns=args.max_turns, attempts=args.attempts, attempt_cap_s=args.attempt_cap_s)
                outf.write(json.dumps(res) + "\n")
                outf.flush()
                print(msg)

    # CSV summary via shared helper
    try:
        rows = []
        with open(out_path, "r", encoding="utf-8") as inf:
            for line in inf:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        if args.agent:
            write_agent_csv(rows, csv_path)
        else:
            write_baseline_csv(rows, csv_path)
        print(f"Wrote results: {out_path}\nWrote CSV: {csv_path}")
        # Auto-append to BENCHMARKS for full-suite agent runs
        if args.agent and args.limit == 0 and not args.no_auto_append:
            try:
                from demas.benchmarks.append import parse_csv, derive_timestamp, append_row
                info = parse_csv(csv_path)
                ts = derive_timestamp(csv_path)
                notes = args.bench_notes or "full suite auto-append"
                append_row("BENCHMARKS.md", ts, info.get("model", ""), info.get("pass_rate", ""), info.get("p50", ""), info.get("p95", ""), notes, info.get("tokens_total", ""))
                print(f"Appended BENCHMARKS row ({notes})")
            except Exception as e:
                print(f"(Auto-append failed): {e}")
    except Exception as e:
        print(f"(CSV summary failed): {e}")

    print(f"Elapsed seconds: {time.time() - t0:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


