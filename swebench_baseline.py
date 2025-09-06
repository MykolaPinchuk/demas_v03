#!/usr/bin/env python3
"""
Non-agent baseline runner:
- Clones a target repo at optional ref
- Installs deps quickly (preinstalled pytest, numpy, pandas in image)
- Runs pytest with an optional -k filter
- Enforces per-stage timeouts to target ≤30s total
- Emits compact JSON result and pytest tail to sandbox/runs/<timestamp>/

Usage examples:
  python swebench_baseline.py --repo https://github.com/pytest-dev/pytest --pytest-k collection
  python swebench_baseline.py --task-id pytest_smoke --repo https://github.com/pytest-dev/pytest --pytest-k collection
"""

import os
import sys
import shlex
import json
import time
import base64
import subprocess
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
from demas.core.docker_exec import run_docker_bash


DOCKER_IMAGE = os.environ.get("SWE_IMAGE", "swebench-lite:py3.10")
WORKDIR = os.path.abspath("sandbox")

# Per-stage timeouts (seconds)
TIMEOUT_CLONE = int(os.environ.get("TIMEOUT_CLONE", "5"))
TIMEOUT_INSTALL = int(os.environ.get("TIMEOUT_INSTALL", "20"))
TIMEOUT_TEST = int(os.environ.get("TIMEOUT_TEST", "5"))


def run_in_container(cmd: str, *, timeout: Optional[int] = None) -> Tuple[int, str, str]:
    return run_docker_bash(cmd, image=DOCKER_IMAGE, workdir=WORKDIR, timeout=timeout)


def nonempty_tail(text: str) -> str:
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _load_seed_task(seed_file: str, task_id: str) -> Optional[Dict[str, Any]]:
    if not task_id:
        return None
    try:
        with open(seed_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("task_id") == task_id:
                    return rec
    except FileNotFoundError:
        return None
    return None


def main(argv: list[str]) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Non-agent baseline SWE runner")
    parser.add_argument("--repo", help="Git repository URL")
    parser.add_argument("--ref", default="", help="Optional git ref/commit")
    parser.add_argument("--pytest-k", default="", help="Optional pytest -k expression")
    parser.add_argument("--task-id", default="", help="Optional task identifier for results")
    parser.add_argument("--seed-file", default=os.path.join("sandbox", "seed_tasks.jsonl"), help="JSONL seeds path")
    parser.add_argument("--patch-file", default="", help="Optional unified diff to apply before tests")
    parser.add_argument("--pre-patch-run", action="store_true", help="Run pytest once before applying patch (records tail_before)")
    args = parser.parse_args(argv)

    # Merge seed task if provided
    seed = _load_seed_task(args.seed_file, args.task_id)
    repo = args.repo or (seed.get("repo") if seed else None)
    ref = args.ref or (seed.get("ref") if seed else "")
    pytest_k_val = args.pytest_k or (seed.get("pytest_k") if seed else "")

    if not repo:
        print("Error: --repo is required if --task-id not found in seed file", file=sys.stderr)
        return 2

    kflag = f'-k "{pytest_k_val}"' if pytest_k_val else ""

    # Optional patch embedding via base64 to avoid quoting issues
    patch_embed = ""
    patch_applied_flag = False
    if args.patch_file:
        try:
            with open(args.patch_file, "rb") as pf:
                b64 = base64.b64encode(pf.read()).decode("ascii")
            patch_embed = (
                "echo '" + b64 + "' > /workspace/patch.b64\n"
                "base64 -d /workspace/patch.b64 > /workspace/patch.diff\n"
                "# apply inside project (we are already cd project)\n"
                f"timeout 3s git apply /workspace/patch.diff && echo PATCH_APPLIED || (echo PATCH_FAILED >&2; exit 3)\n"
            )
            patch_applied_flag = True
        except Exception:
            patch_embed = ""
            patch_applied_flag = False

    # Build a single-session script with per-step timeouts using coreutils `timeout`
    # If `timeout` is unavailable, outer timeout in run_in_container still caps the whole run.
    # Optional pre-run before applying patch, then apply patch, then run tests again.
    pre_run_cmd = (
        f"btail=$(timeout {TIMEOUT_TEST}s python -m pytest -q {kflag} | tail -n 1)\n"
        "echo BEFORE_TAIL: ${btail}\n"
    ) if args.pre_patch_run else ""

    post_run_cmd = (
        f"atail=$(timeout {TIMEOUT_TEST}s python -m pytest -q {kflag} | tail -n 1)\n"
        "echo AFTER_TAIL: ${atail}\n"
    )

    bash_script = f"""
set -e
rm -rf project
timeout {TIMEOUT_CLONE}s git clone --depth 1 {shlex.quote(repo)} project
cd project
if [ -n {shlex.quote(ref or '')} ]; then \
  timeout {TIMEOUT_CLONE}s git fetch --depth 1 origin {shlex.quote(ref)} && \
  git checkout -q {shlex.quote(ref)}; \
fi
python -m pip install -q -U pip
# Common build backends used by modern projects
timeout 10s python -m pip install -q hatchling hatch-vcs || true
# Editable install of the project (fast fail if not needed)
timeout {TIMEOUT_INSTALL}s python -m pip install -q -e . || true
# Project-specific test requirements if present
if [ -f testing/requirements.txt ]; then \
  timeout {TIMEOUT_INSTALL}s python -m pip install -q -r testing/requirements.txt; \
fi
# Optional pre-patch run
{pre_run_cmd}
# Apply patch if provided
{patch_embed}
# Run tests after (or only run if no pre-patch)
{post_run_cmd}
"""

    t0 = time.time()
    code, out, err = run_in_container(bash_script)
    elapsed = time.time() - t0
    # Extract BEFORE/AFTER tails if present
    before_tail = ""
    after_tail = ""
    for ln in (out or "").splitlines():
        if ln.startswith("BEFORE_TAIL:"):
            before_tail = ln.split(":", 1)[1].strip()
        if ln.startswith("AFTER_TAIL:"):
            after_tail = ln.split(":", 1)[1].strip()
    tail = after_tail or nonempty_tail(out) or nonempty_tail(err) or "(no output)"

    status = "pass" if (" passed" in tail and " failed" not in tail and " error" not in tail) else ("fail" if code != 0 else "ok")

    # Prepare result directory
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(WORKDIR, "runs", ts)
    os.makedirs(run_dir, exist_ok=True)

    # Write artifacts
    with open(os.path.join(run_dir, "pytest_tail.txt"), "w", encoding="utf-8") as f:
        f.write(tail + "\n")

    result = {
        "task_id": args.task_id or "",
        "repo": repo,
        "ref": ref,
        "pytest_k": pytest_k_val,
        "status": status,
        "exit_code": code,
        "duration_s": round(elapsed, 3),
        "tail": tail,
        "patch_applied": bool(args.patch_file) and patch_applied_flag,
        "tail_before": before_tail if args.pre_patch_run else "",
        "status_before": (
            ("pass" if (" passed" in before_tail and " failed" not in before_tail and " error" not in before_tail) else ("fail" if before_tail else ""))
            if args.pre_patch_run else ""
        ),
    }
    with open(os.path.join(run_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(tail)
    # Return 0 even on test failure to keep orchestration simple; status is in JSON
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


