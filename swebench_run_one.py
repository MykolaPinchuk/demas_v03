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


def run_agent(task: Dict[str, Any]) -> int:
    env = os.environ.copy()
    env.setdefault("SWE_IMAGE", "swebench-lite:py3.10")
    env["TARGET_REPO"] = task.get("repo", "")
    env["TARGET_REF"] = task.get("ref", "")
    env["PYTEST_K"] = task.get("pytest_k", "")
    if not env.get("CHUTES_API_KEY"):
        raise SystemExit("CHUTES_API_KEY not set")
    subprocess.run([sys.executable, os.path.join(ROOT, "team_swebench_oneagent.py")], env=env, check=False)
    return 0


def main(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Run one SWE task (baseline or agent)")
    parser.add_argument("--tasks", default=os.path.join(ROOT, "sandbox", "swe_tasks.jsonl"))
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--agent", action="store_true", help="Use agent mode instead of baseline")
    args = parser.parse_args(argv)

    task = load_task(args.tasks, args.task_id)
    if args.agent:
        return run_agent(task)
    else:
        return run_baseline(task)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


