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
from demas.core import config as _cfg
from demas.core.io import extract_pytest_tail


DOCKER_IMAGE = _cfg.DOCKER_IMAGE
WORKDIR = _cfg.WORKDIR

# Per-stage timeouts (seconds)
TIMEOUT_CLONE = _cfg.TIMEOUT_CLONE
TIMEOUT_INSTALL = _cfg.TIMEOUT_INSTALL
TIMEOUT_TEST = _cfg.TIMEOUT_TEST


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

    # Use a unique project directory per run to avoid collisions under parallel jobs
    proj_dir = f"project_{int(time.time()*1000)}_{os.getpid()}"
    proj_q = shlex.quote(proj_dir)

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
rm -rf {proj_q}
echo STAGE:CLONE:START $(date +%s.%N)
timeout {TIMEOUT_CLONE}s git clone --depth 1 {shlex.quote(repo)} {proj_q}
cd {proj_q}
if [ -n {shlex.quote(ref or '')} ]; then \
  timeout {TIMEOUT_CLONE}s git fetch --depth 1 origin {shlex.quote(ref)} && \
  git checkout -q {shlex.quote(ref)}; \
fi
echo STAGE:CLONE:END $(date +%s.%N)

echo STAGE:INSTALL:START $(date +%s.%N)
python -m pip install -q -U pip || true
# Common build backends used by modern projects
timeout 10s python -m pip install -q hatchling hatch-vcs meson-python ninja cython setuptools_scm || true
# Editable install of the project; fallback to regular install if needed
timeout {TIMEOUT_INSTALL}s python -m pip install -q -e . || timeout {TIMEOUT_INSTALL}s python -m pip install -q . || true
# Root requirements if present
if [ -f requirements.txt ]; then \
  timeout {TIMEOUT_INSTALL}s python -m pip install -q -r requirements.txt || true; \
fi
# Project-specific test requirements if present
if [ -f testing/requirements.txt ]; then \
  timeout {TIMEOUT_INSTALL}s python -m pip install -q -r testing/requirements.txt || true; \
fi
# dateutil zoneinfo tarball generation if missing (tests expect packaged DB)
if [ -d src/dateutil/zoneinfo ]; then \
  if [ ! -f src/dateutil/zoneinfo/dateutil-zoneinfo.tar.gz ]; then \
    timeout 10s python updatezinfo.py || true; \
    if [ -f dateutil/zoneinfo/dateutil-zoneinfo.tar.gz ]; then cp -f dateutil/zoneinfo/dateutil-zoneinfo.tar.gz src/dateutil/zoneinfo/; fi; \
    if [ ! -f src/dateutil/zoneinfo/dateutil-zoneinfo.tar.gz ]; then \
      mkdir -p /workspace/_deps_tmp && \
      timeout 15s python -m pip download -q python-dateutil -d /workspace/_deps_tmp || true; \
      python - <<'PY' || true\nimport zipfile,sys\nfrom pathlib import Path\nwhl = next(iter(Path('/workspace/_deps_tmp').glob('python_dateutil-*.whl')), None)\nif whl:\n    with zipfile.ZipFile(str(whl),'r') as z:\n        try:\n            z.extract('dateutil/zoneinfo/dateutil-zoneinfo.tar.gz','/workspace/_deps_tmp')\n        except Exception:\n            pass\nPY\n; \
      if [ -f /workspace/_deps_tmp/dateutil/zoneinfo/dateutil-zoneinfo.tar.gz ]; then cp -f /workspace/_deps_tmp/dateutil/zoneinfo/dateutil-zoneinfo.tar.gz src/dateutil/zoneinfo/; fi; \
    fi; \
  fi; \
fi
echo STAGE:INSTALL:END $(date +%s.%N)

# Optional pre-patch run
{pre_run_cmd}
# Apply patch if provided
{patch_embed}
# Run tests after (or only run if no pre-patch)
echo STAGE:TEST:START $(date +%s.%N)
{post_run_cmd}
echo STAGE:TEST:END $(date +%s.%N)
"""

    t0 = time.time()
    code, out, err = run_in_container(bash_script)
    elapsed = time.time() - t0
    # Extract BEFORE/AFTER tails and stage timings if present
    before_tail = ""
    after_tail = ""
    t_markers = {"CLONE": {"start": None, "end": None}, "INSTALL": {"start": None, "end": None}, "TEST": {"start": None, "end": None}}
    for ln in (out or "").splitlines():
        if ln.startswith("BEFORE_TAIL:"):
            before_tail = ln.split(":", 1)[1].strip()
        if ln.startswith("AFTER_TAIL:"):
            after_tail = ln.split(":", 1)[1].strip()
        if ln.startswith("STAGE:"):
            try:
                parts = ln.strip().split()
                tag = parts[0]  # e.g., STAGE:CLONE:START
                ts = float(parts[1]) if len(parts) > 1 else None
                _, stage, kind = tag.split(":", 2)
                if stage in t_markers and kind.lower() in ("start", "end") and ts is not None:
                    t_markers[stage][kind.lower()] = ts
            except Exception:
                pass
    tail = after_tail or extract_pytest_tail(out, err)

    status = "pass" if (" passed" in tail and " failed" not in tail and " error" not in tail) else ("fail" if code != 0 else "ok")

    # Prepare result directory (allow caller to override for parallel safety)
    ts = os.environ.get("RUN_TS") or datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(WORKDIR, "runs", ts)
    os.makedirs(run_dir, exist_ok=True)

    # Write artifacts
    with open(os.path.join(run_dir, "pytest_tail.txt"), "w", encoding="utf-8") as f:
        f.write(tail + "\n")

    # Compute durations if both start/end are present
    def _dur(stage: str) -> float:
        st = t_markers.get(stage, {}).get("start")
        en = t_markers.get(stage, {}).get("end")
        if isinstance(st, float) and isinstance(en, float) and en >= st:
            return round(en - st, 3)
        return 0.0

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
        "duration_clone_s": _dur("CLONE"),
        "duration_install_s": _dur("INSTALL"),
        "duration_test_s": _dur("TEST"),
    }
    with open(os.path.join(run_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    print(tail)
    # Return 0 even on test failure to keep orchestration simple; status is in JSON
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))


