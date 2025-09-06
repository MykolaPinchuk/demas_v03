#!/usr/bin/env python3
import os
import sys
import json
import base64
import subprocess
from typing import Dict, Any, Optional

ROOT = os.path.abspath(os.path.dirname(__file__))


def load_task(tasks_path: str, task_id: str) -> Dict[str, Any]:
    with open(tasks_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("task_id") == task_id:
                return rec
    raise SystemExit(f"Task '{task_id}' not found in {tasks_path}")


def run_baseline(task: Dict[str, Any]) -> int:
    args = [sys.executable, os.path.join(ROOT, "swebench_baseline.py"), "--repo", task["repo"], "--task-id", task["task_id"]]
    if task.get("ref"):
        args += ["--ref", task["ref"]]
    if task.get("pytest_k"):
        args += ["--pytest-k", task["pytest_k"]]
    if task.get("patch_b64"):
        # write patch to temp file
        patch_path = os.path.join(ROOT, "sandbox", "_task.patch")
        with open(patch_path, "wb") as pf:
            pf.write(base64.b64decode(task["patch_b64"]))
        args += ["--patch-file", patch_path, "--pre-patch-run"]
    # Per-task timeouts via env
    env = os.environ.copy()
    to = task.get("timeouts", {}) or {}
    if isinstance(to, dict):
        if to.get("clone"):
            env["TIMEOUT_CLONE"] = str(int(to["clone"]))
        if to.get("install"):
            env["TIMEOUT_INSTALL"] = str(int(to["install"]))
        if to.get("test"):
            env["TIMEOUT_TEST"] = str(int(to["test"]))
    subprocess.run(args, check=False, env=env)
    return 0


def run_agent(task: Dict[str, Any], *, model: str, temperature: float, max_turns: int) -> int:
    env = os.environ.copy()
    env.setdefault("SWE_IMAGE", "swebench-lite:py3.10")
    env["TARGET_REPO"] = task.get("repo", "")
    env["TARGET_REF"] = task.get("ref", "")
    env["PYTEST_K"] = task.get("pytest_k", "")
    # per-task timeouts
    to = task.get("timeouts", {}) or {}
    if isinstance(to, dict):
        if to.get("clone"):
            env["TIMEOUT_CLONE"] = str(int(to["clone"]))
        if to.get("install"):
            env["TIMEOUT_INSTALL"] = str(int(to["install"]))
        if to.get("test"):
            env["TIMEOUT_TEST"] = str(int(to["test"]))
    # logging base dir
    from datetime import datetime
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(ROOT, "sandbox", "agent_batch_runs", ts)
    os.makedirs(os.path.join(out_dir, "logs"), exist_ok=True)
    env["RUN_BASE_DIR"] = out_dir
    env["TASK_ID"] = task.get("task_id", "single")
    # model config
    if model:
        env["MODEL_NAME"] = model
    if temperature is not None:
        env["MODEL_TEMPERATURE"] = str(temperature)
    if max_turns:
        env["MAX_TURNS"] = str(int(max_turns))
    if not env.get("CHUTES_API_KEY"):
        raise SystemExit("CHUTES_API_KEY not set")
    subprocess.run([sys.executable, "-m", "demas.swe.oneagent"], env=env, check=False)
    return 0


def main(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(
        description="Run a single SWE-style task. Baseline by default; use --agent for the one-agent flow.")
    parser.add_argument(
        "--tasks",
        default=os.path.join(ROOT, "sandbox", "swe_tasks.jsonl"),
        help="Path to local tasks JSONL (default: sandbox/swe_tasks.jsonl)")
    parser.add_argument(
        "--swe-input",
        default=os.path.join(ROOT, "sandbox", "swe_official.jsonl"),
        help="Optional SWE official JSONL; used if --task-id not found in --tasks (adapter path)")
    parser.add_argument("--task-id", required=True, help="Task identifier to run")
    parser.add_argument(
        "--agent",
        action="store_true",
        help="Use agent mode instead of baseline (requires CHUTES_API_KEY)")
    parser.add_argument(
        "--model",
        default=os.environ.get("MODEL_NAME", ""),
        help="Model name for agent mode (env MODEL_NAME as default; e.g., moonshotai/Kimi-K2-Instruct-0905)")
    parser.add_argument(
        "--temperature",
        type=float,
        default=float(os.environ.get("MODEL_TEMPERATURE", "0.2")),
        help="Sampling temperature for agent mode (default from env MODEL_TEMPERATURE or 0.2)")
    parser.add_argument(
        "--max-turns",
        dest="max_turns",
        type=int,
        default=int(os.environ.get("MAX_TURNS", "10")),
        help="Maximum agent turns before termination (default from env MAX_TURNS or 10)")
    args = parser.parse_args(argv)

    # Try local tasks first; if not found, try adapter input
    try:
        task = load_task(args.tasks, args.task_id)
    except SystemExit:
        from demas.adapters.swebench import load_official_tasks
        alt = load_official_tasks(args.swe_input)
        found = [t for t in alt if t.get("task_id") == args.task_id]
        if not found:
            raise
        task = found[0]
    if args.agent:
        return run_agent(task, model=args.model, temperature=args.temperature, max_turns=args.max_turns)
    else:
        return run_baseline(task)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


