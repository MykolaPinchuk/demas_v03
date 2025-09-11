# team_swebench_oneagent.py
# One-agent MVP for repo validation in Docker with robust termination.
# pip install -U autogen-agentchat autogen-ext[openai]
# docker build -f Dockerfile.swe -t swebench-lite:py3.10 .

import os, shlex, time, asyncio, subprocess, json, uuid
from datetime import datetime
from typing import List, Optional, Callable, Any, Dict

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.ui import Console

from autogen_core.models import UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient
from demas.core import config as _cfg
from demas.core.io import extract_pytest_tail
from demas.core.docker_exec import run_docker_bash

# ---------------- config ----------------
CHUTES_API_KEY  = os.environ.get("CHUTES_API_KEY")
CHUTES_BASE_URL = os.environ.get("CHUTES_BASE_URL", "https://llm.chutes.ai/v1")

# OpenRouter support (auto-routed for specific models)
OPENROUTER_API_KEY  = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

MODEL_CANDIDATES: List[str] = [
    # Prefer non-OpenAI models via Chutes first
    "moonshotai/Kimi-K2-Instruct-75k",
    "deepseek-ai/DeepSeek-V3-0324",
    # OpenRouter cheap models (only used if OpenRouter key is set)
    "openai/gpt-5-mini",
    "openai/gpt-oss-120b",
]
BASE_MODEL_INFO = {
    "vision": False, "function_calling": True,
    "json_output": False, "structured_output": False, "family": "unknown",
}

DOCKER_IMAGE   = _cfg.DOCKER_IMAGE
MAX_TURNS      = int(os.environ.get("MAX_TURNS", "10"))  # allow diagnostics, install, and one patch attempt

# Per-stage timeouts (seconds), aligned with baseline runner
TIMEOUT_CLONE  = _cfg.TIMEOUT_CLONE
TIMEOUT_INSTALL= _cfg.TIMEOUT_INSTALL
TIMEOUT_TEST   = _cfg.TIMEOUT_TEST
DEPS_DIR      = "/workspace/_deps"  # persisted on host via volume mount

TARGET_REPO = os.environ.get("TARGET_REPO", "https://github.com/pytest-dev/pytest")
TARGET_REF  = os.environ.get("TARGET_REF", "")
PYTEST_K    = os.environ.get("PYTEST_K", "")  # default to empty (no filter)
PROJECT_DIR = os.environ.get("PROJECT_DIR", None)

# Model override via env
MODEL_NAME = os.environ.get("MODEL_NAME", "")
MODEL_TEMPERATURE = float(os.environ.get("MODEL_TEMPERATURE", "0.2"))

# Logging config
RUN_BASE_DIR = os.environ.get("RUN_BASE_DIR", "")
TASK_ID = os.environ.get("TASK_ID", "")
RUN_ID = str(uuid.uuid4())
LOG_DIR = os.path.join(RUN_BASE_DIR, "logs") if RUN_BASE_DIR else ""
LOG_PATH = os.path.join(LOG_DIR, f"{TASK_ID or 'task'}.jsonl") if LOG_DIR else ""
ATTEMPT_HINT = os.environ.get("ATTEMPT_HINT", "").strip()

# ------------- model + preflight -------------
def _provider_for_model(model_name: str) -> str:
    name = (model_name or "").lower()
    # Route any openai/* models to OpenRouter by default
    if name.startswith("openai/"):
        return "openrouter"
    return "chutes"


def make_client(model_name: str, *, temperature: float) -> OpenAIChatCompletionClient:
    provider = _provider_for_model(model_name)
    if provider == "openrouter":
        if not OPENROUTER_API_KEY:
            raise RuntimeError("OPENROUTER_API_KEY is not set but required for model '%s'" % model_name)
        client = OpenAIChatCompletionClient(
            model=model_name,
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            temperature=temperature,
            include_name_in_message=True,
            model_info=BASE_MODEL_INFO,
        )
        return _enable_usage_injection(client)
    # Default provider: Chutes
    client = OpenAIChatCompletionClient(
        model=model_name,
        api_key=CHUTES_API_KEY,
        base_url=CHUTES_BASE_URL,
        temperature=temperature,
        include_name_in_message=True,
        model_info=BASE_MODEL_INFO,
    )
    return _enable_usage_injection(client)


def _enable_usage_injection(client: OpenAIChatCompletionClient) -> OpenAIChatCompletionClient:
    # No-op: token usage capture removed for now
    return client

async def preflight(client: OpenAIChatCompletionClient) -> bool:
    try:
        stream = client.create_stream(
            messages=[UserMessage(content="hi", source="user")],
            extra_create_args={"max_tokens": 4, "stream_options": {"include_usage": True}},
        )
        async for _ in stream:
            pass
        return True
    except Exception:
        return False

async def pick_ready_model() -> OpenAIChatCompletionClient:
    # If a specific model is requested, use it directly
    if MODEL_NAME:
        c = make_client(MODEL_NAME, temperature=MODEL_TEMPERATURE)
        # Skip preflight for OpenRouter to avoid false negatives on stream quirks
        if _provider_for_model(MODEL_NAME) == "openrouter":
            print(f"[preflight] Skipping preflight; using OpenRouter model: {MODEL_NAME}")
            return c
        # For Chutes, keep a quick preflight
        ok = await preflight(c)
        if ok:
            print(f"[preflight] Using model: {MODEL_NAME}")
            return c
        raise RuntimeError(f"Requested model not available: {MODEL_NAME}")
    for m in MODEL_CANDIDATES:
        c = make_client(m, temperature=MODEL_TEMPERATURE)
        if _provider_for_model(m) == "openrouter":
            print(f"[preflight] Skipping preflight; using OpenRouter model: {m}")
            return c
        if await preflight(c):
            print(f"[preflight] Using model: {m}")
            return c
        print(f"[preflight] Model not ready: {m} -> next")
    raise RuntimeError("No model available for now.")

# ---------------- docker helpers ----------------
def ensure_docker_image() -> None:
    try:
        p = subprocess.run(["docker", "image", "inspect", DOCKER_IMAGE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if p.returncode != 0:
            # Build from repository root where Dockerfile.swe resides
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            df = os.path.join(repo_root, "Dockerfile.swe")
            if not os.path.isfile(df):
                print(f"[warn] Dockerfile.swe not found at {df}; cannot auto-build image {DOCKER_IMAGE}")
                return
            print(f"[auto-build] Building missing image {DOCKER_IMAGE} from Dockerfile.swe...")
            subprocess.run(["docker", "build", "-f", df, "-t", DOCKER_IMAGE, repo_root], check=False)
    except Exception:
        pass

def _docker(cmd: str) -> tuple[int, str, str]:
    return run_docker_bash(cmd, image=DOCKER_IMAGE, workdir="sandbox")

# -------- logging helpers --------
def _ensure_log_dir() -> None:
    if LOG_DIR:
        os.makedirs(LOG_DIR, exist_ok=True)

def _truncate(s: str, limit: int = 8192) -> str:
    if s is None:
        return ""
    if len(s) <= limit:
        return s
    return s[:limit] + "...<truncated>"

def _redact(obj: Any) -> Any:
    try:
        if isinstance(obj, dict):
            redacted: Dict[str, Any] = {}
            for k, v in obj.items():
                if any(x in k.lower() for x in ["api_key", "apikey", "authorization", "token", "secret"]):
                    redacted[k] = "***REDACTED***"
                else:
                    redacted[k] = _redact(v)
            return redacted
        if isinstance(obj, list):
            return [_redact(x) for x in obj]
        return obj
    except Exception:
        return obj

def _log_record(record: Dict[str, Any]) -> None:
    if not LOG_PATH:
        return
    _ensure_log_dir()
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

# ---- tools (must be async functions with type hints) ----
async def swe_clone(*, repo_url: str, ref: Optional[str] = None) -> str:
    _log_record({
        "timestamp": _now_iso(), "role": "assistant", "content": "CALL swe_clone",
        "tool_name": "swe_clone", "tool_args": _redact({"repo_url": repo_url, "ref": ref}),
        "tool_result": "", "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })
    # Determine a unique project directory name
    proj = PROJECT_DIR or f"project_{(TASK_ID or 'task').replace('/', '_')}_{RUN_ID[:8]}"
    proj_q = shlex.quote(proj)
    cmds = [
        f"rm -rf {proj_q}",
        f"timeout {TIMEOUT_CLONE}s git clone --depth 1 {shlex.quote(repo_url)} {proj_q}",
    ]
    if ref:
        cmds.append(
            f"cd {proj_q} && timeout {TIMEOUT_CLONE}s git fetch --depth 1 origin {shlex.quote(ref)} && git checkout -q {shlex.quote(ref)}"
        )
    code, out, err = _docker(" && ".join(cmds))
    res = "(cloned)" if code == 0 else f"(exit {code})\nSTDOUT:\n{out}\nSTDERR:\n{err}"
    _log_record({
        "timestamp": _now_iso(), "role": "tool", "content": "", "tool_name": "swe_clone",
        "tool_args": _redact({"repo_url": repo_url, "ref": ref}),
        "tool_result": _truncate(res), "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })
    return res

async def swe_install(*, req_file: str = "requirements.txt") -> str:
    proj = PROJECT_DIR or f"project_{(TASK_ID or 'task').replace('/', '_')}_{RUN_ID[:8]}"
    proj_q = shlex.quote(proj)
    cmd = (
        f"cd {proj_q} && "
        "python -m pip install -q -U pip && "
        "timeout 10s python -m pip install -q hatchling hatch-vcs meson-python ninja cython || true && "
        # Try editable install first, then fallback to regular install if it fails
        f"(timeout {TIMEOUT_INSTALL}s python -m pip install -q -e . || timeout {TIMEOUT_INSTALL}s python -m pip install -q . || true) && "
        # If meson build artifacts exist, copy compiled .so into package dir to persist
        "if [ -d build ]; then so=$(find build -name '*_cfinancial*.so' | head -n1); "
        "if [ -n \"$so\" ]; then cp -f \"$so\" numpy_financial/; fi; fi && "
        # dateutil zoneinfo tarball generation if missing (tests expect packaged DB)
        "if [ -d src/dateutil/zoneinfo ]; then "
        "  if [ ! -f src/dateutil/zoneinfo/dateutil-zoneinfo.tar.gz ]; then "
        "    timeout 10s python updatezinfo.py || true; "
        "    if [ -f dateutil/zoneinfo/dateutil-zoneinfo.tar.gz ]; then cp -f dateutil/zoneinfo/dateutil-zoneinfo.tar.gz src/dateutil/zoneinfo/; fi; "
        "  fi; "
        "fi && "
        f"if [ -f {shlex.quote(req_file)} ]; then timeout {TIMEOUT_INSTALL}s python -m pip install -q -r {shlex.quote(req_file)}; else echo 'no requirements.txt'; fi && "
        # testing requirements if present
        f"if [ -f testing/requirements.txt ]; then timeout {TIMEOUT_INSTALL}s python -m pip install -q -r testing/requirements.txt; else echo 'no testing/requirements.txt'; fi"
    )
    _log_record({
        "timestamp": _now_iso(), "role": "assistant", "content": "CALL swe_install",
        "tool_name": "swe_install", "tool_args": _redact({"req_file": req_file}),
        "tool_result": "", "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })
    code, out, err = _docker(cmd)
    res = (out or "ok").strip() if code == 0 else f"(exit {code})\nSTDOUT:\n{out}\nSTDERR:\n{err}"
    _log_record({
        "timestamp": _now_iso(), "role": "tool", "content": "", "tool_name": "swe_install",
        "tool_args": _redact({"req_file": req_file}),
        "tool_result": _truncate(res), "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })
    return res

async def swe_pytest_auto(*, pytest_args: str = "-q") -> str:
    """Run pytest; if ModuleNotFoundError occurs, attempt to install the missing
    module via pip (site-packages under DEPS_DIR), then re-run tests once.
    Returns the final pytest tail line or a brief diagnostic string.
    """
    # Log call
    _log_record({
        "timestamp": _now_iso(), "role": "assistant", "content": "CALL swe_pytest_auto",
        "tool_name": "swe_pytest_auto", "tool_args": _redact({"pytest_args": pytest_args}),
        "tool_result": "", "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })

    # First attempt
    proj = PROJECT_DIR or f"project_{(TASK_ID or 'task').replace('/', '_')}_{RUN_ID[:8]}"
    proj_q = shlex.quote(proj)
    cmd = (
        f"export PYTHONPATH=/workspace/{proj}:/workspace/{proj}/src:{DEPS_DIR}:$PYTHONPATH; "
        f"cd {proj_q} && timeout {TIMEOUT_TEST}s python -m pytest {pytest_args}"
    )
    code, out, err = _docker(cmd)
    combined = (out or "") + ("\n" + err if err else "")
    tail = extract_pytest_tail(out, err)

    # Detect ModuleNotFoundError
    missing = None
    for line in combined.splitlines():
        line = line.strip()
        if "ModuleNotFoundError:" in line and "No module named" in line:
            # try to extract 'package' from No module named 'package'
            import re
            m = re.search(r"No module named ['\"]([A-Za-z0-9_\-\.]+)['\"]", line)
            if m:
                missing = m.group(1)
                break

    if missing:
        # Attempt to install the missing module
        _log_record({
            "timestamp": _now_iso(), "role": "assistant", "content": f"Detected missing module: {missing}; attempting pip install",
            "tool_name": "swe_pytest_auto", "tool_args": _redact({"missing": missing}),
            "tool_result": "", "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
            "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
        })
        # Prefer installing the top-level package name
        top_pkg = missing.split(".")[0]
        # Try re-running local install to capture src-layout packages
        try:
            _ = await swe_install()
        except Exception:
            pass
        # Verify import with local path first
        verify_cmd = (
            f"export PYTHONPATH=/workspace/{proj}:{DEPS_DIR}:$PYTHONPATH; "
            f"python -c 'import {top_pkg}; print(\"ok\")'"
        )
        vcode, vout, verr = _docker(verify_cmd)
        if vcode != 0:
            # Install via pip into deps dir
            try:
                install_res = await swe_pip_install(packages=top_pkg)
                _log_record({
                    "timestamp": _now_iso(), "role": "tool", "content": "", "tool_name": "swe_pip_install",
                    "tool_args": _redact({"packages": top_pkg}),
                    "tool_result": _truncate(install_res), "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
                    "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
                })
            except Exception as e:
                _log_record({
                    "timestamp": _now_iso(), "role": "tool", "content": "", "tool_name": "swe_pip_install",
                    "tool_args": _redact({"packages": top_pkg}),
                    "tool_result": _truncate(f"install_error: {e}"), "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
                    "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
                })
        # Re-run pytest and return the tail
        code2, out2, err2 = _docker(cmd)
        tail2 = extract_pytest_tail(out2, err2)
        res = tail2 or tail or "(no stdout)"
        _log_record({
            "timestamp": _now_iso(), "role": "tool", "content": "", "tool_name": "swe_pytest_auto",
            "tool_args": _redact({"pytest_args": pytest_args}),
            "tool_result": _truncate(res), "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
            "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
        })
        return res

    # No missing module detected; if tests succeeded but we didn't capture a pytest
    # summary line, run a quick summary-only pass to get a proper tail that contains
    # " passed" so termination can trigger reliably.
    if code == 0 and ((" passed" not in tail) or not tail.strip()):
        code_s, out_s, err_s = _docker(
            f"export PYTHONPATH=/workspace/{proj}:/workspace/{proj}/src:{DEPS_DIR}:$PYTHONPATH; "
            f"cd {proj_q} && timeout {TIMEOUT_TEST}s python -m pytest -q | tail -n 1"
        )
        last_s = [ln for ln in (out_s or "").splitlines() if ln.strip()]
        if last_s:
            tail = last_s[-1]
    # No missing module detected; return final tail
    res = tail or "(no stdout)"
    _log_record({
        "timestamp": _now_iso(), "role": "tool", "content": "", "tool_name": "swe_pytest_auto",
        "tool_args": _redact({"pytest_args": pytest_args}),
        "tool_result": _truncate(res), "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })
    return res

async def swe_pytest(*, pytest_args: str = "-q") -> str:
    proj = PROJECT_DIR or f"project_{(TASK_ID or 'task').replace('/', '_')}_{RUN_ID[:8]}"
    proj_q = shlex.quote(proj)
    cmd = (
        f"export PYTHONPATH=/workspace/{proj}:/workspace/{proj}/src:{DEPS_DIR}:$PYTHONPATH; "
        f"cd {proj_q} && timeout {TIMEOUT_TEST}s python -m pytest {pytest_args}"
    )
    _log_record({
        "timestamp": _now_iso(), "role": "assistant", "content": "CALL swe_pytest",
        "tool_name": "swe_pytest", "tool_args": _redact({"pytest_args": pytest_args}),
        "tool_result": "", "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })
    code, out, err = _docker(cmd)
    tail = extract_pytest_tail(out, err)
    res = tail or "(no stdout)"
    _log_record({
        "timestamp": _now_iso(), "role": "tool", "content": "", "tool_name": "swe_pytest",
        "tool_args": _redact({"pytest_args": pytest_args}),
        "tool_result": _truncate(res), "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })
    return res

async def swe_pytest_full(*, pytest_args: str = "-q -x -vv") -> str:
    """Run pytest and return the last ~200 lines of combined stdout+stderr, with ' passed' sanitized
    to avoid triggering termination conditions inadvertently."""
    proj = PROJECT_DIR or f"project_{(TASK_ID or 'task').replace('/', '_')}_{RUN_ID[:8]}"
    proj_q = shlex.quote(proj)
    cmd = (
        f"export PYTHONPATH=/workspace/{proj}:/workspace/{proj}/src:{DEPS_DIR}:$PYTHONPATH; "
        f"cd {proj_q} && timeout {TIMEOUT_TEST}s python -m pytest {pytest_args}"
    )
    _log_record({
        "timestamp": _now_iso(), "role": "assistant", "content": "CALL swe_pytest_full",
        "tool_name": "swe_pytest_full", "tool_args": _redact({"pytest_args": pytest_args}),
        "tool_result": "", "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })
    code, out, err = _docker(cmd)
    text = (out or "") + ("\n" + err if err else "")
    lines = [ln for ln in text.splitlines() if ln is not None]
    tail_block = "\n".join(lines[-200:])
    safe = tail_block.replace(" passed in ", " p✓ssed in ").replace(" passed", " p✓ssed")
    res = safe or "(no output)"
    _log_record({
        "timestamp": _now_iso(), "role": "tool", "content": "", "tool_name": "swe_pytest_full",
        "tool_args": _redact({"pytest_args": pytest_args}),
        "tool_result": _truncate(res), "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })
    return res

async def swe_read_file(*, path: str, max_bytes: int = 20000) -> str:
    """Read a file inside the project (relative path), returning up to max_bytes."""
    rp = shlex.quote(path)
    mb = max(1, int(max_bytes))
    proj = PROJECT_DIR or f"project_{(TASK_ID or 'task').replace('/', '_')}_{RUN_ID[:8]}"
    proj_q = shlex.quote(proj)
    cmd = (
        f"cd {proj_q} && if [ -f {rp} ]; then head -c {mb} -- {rp}; else echo '(file not found)'; fi"
    )
    _log_record({
        "timestamp": _now_iso(), "role": "assistant", "content": "CALL swe_read_file",
        "tool_name": "swe_read_file", "tool_args": _redact({"path": path, "max_bytes": max_bytes}),
        "tool_result": "", "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })
    code, out, err = _docker(cmd)
    res = (out or "(empty)") if code == 0 else f"(exit {code})\nSTDOUT:\n{out}\nSTDERR:\n{err}"
    _log_record({
        "timestamp": _now_iso(), "role": "tool", "content": "", "tool_name": "swe_read_file",
        "tool_args": _redact({"path": path, "max_bytes": max_bytes}),
        "tool_result": _truncate(res), "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })
    return res

async def swe_pip_install(*, packages: str) -> str:
    """Install one or more packages via pip (space-separated)."""
    pk = packages.strip()
    if not pk:
        return "(no packages)"
    cmd = (
        f"mkdir -p {DEPS_DIR} && "
        f"timeout {TIMEOUT_INSTALL}s python -m pip install -q -t {DEPS_DIR} {shlex.quote(pk)}"
    )
    _log_record({
        "timestamp": _now_iso(), "role": "assistant", "content": "CALL swe_pip_install",
        "tool_name": "swe_pip_install", "tool_args": _redact({"packages": packages}),
        "tool_result": "", "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })
    code, out, err = _docker(cmd)
    res = "ok" if code == 0 else f"(exit {code})\nSTDOUT:\n{out}\nSTDERR:\n{err}"
    _log_record({
        "timestamp": _now_iso(), "role": "tool", "content": "", "tool_name": "swe_pip_install",
        "tool_args": _redact({"packages": packages}),
        "tool_result": _truncate(res), "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })
    return res
async def swe_apply_patch_text(*, diff_text: str) -> str:
    # Write diff into workspace and apply within the repo
    _log_record({
        "timestamp": _now_iso(), "role": "assistant", "content": "CALL swe_apply_patch_text",
        "tool_name": "swe_apply_patch_text",
        "tool_args": _redact({"diff_text": f"<diff_len={len(diff_text)}>"}),
        "tool_result": "", "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })
    proj = PROJECT_DIR or f"project_{(TASK_ID or 'task').replace('/', '_')}_{RUN_ID[:8]}"
    script = (
        "set -e\n"
        "cd /workspace\n"
        "printf '%s' \"" + diff_text.replace("\\", "\\\\").replace("\"", "\\\"") + "\" > patch.diff\n"
        f"cd {shlex.quote(proj)}\n"
        "timeout 3s git apply /workspace/patch.diff && echo PATCH_APPLIED || (echo PATCH_FAILED >&2; exit 3)\n"
    )
    code, out, err = _docker(script)
    res = (out or "").strip() if code == 0 else f"(exit {code})\nSTDOUT:\n{out}\nSTDERR:\n{err}"
    _log_record({
        "timestamp": _now_iso(), "role": "tool", "content": "", "tool_name": "swe_apply_patch_text",
        "tool_args": _redact({"diff_text": f"<diff_len={len(diff_text)}>"}),
        "tool_result": _truncate(res), "usage": None, "run_id": RUN_ID, "task_id": TASK_ID,
        "model": MODEL_NAME or None, "temperature": MODEL_TEMPERATURE,
    })
    return res

# ------------- tool wrappers for logging -------------
def _wrap_tool(func: Callable[..., Any], name: str) -> Callable[..., Any]:
    async def _wrapped(**kwargs):
        # log call
        _log_record({
            "timestamp": _now_iso(),
            "role": "assistant",
            "content": f"CALL {name}",
            "tool_name": name,
            "tool_args": _redact(kwargs),
            "tool_result": "",
            "usage": None,
            "run_id": RUN_ID,
            "task_id": TASK_ID,
            "model": MODEL_NAME or None,
            "temperature": MODEL_TEMPERATURE,
        })
        res = await func(**kwargs)
        _log_record({
            "timestamp": _now_iso(),
            "role": "tool",
            "content": "",
            "tool_name": name,
            "tool_args": _redact(kwargs),
            "tool_result": _truncate(res if isinstance(res, str) else str(res)),
            "usage": None,
            "run_id": RUN_ID,
            "task_id": TASK_ID,
            "model": MODEL_NAME or None,
            "temperature": MODEL_TEMPERATURE,
        })
        return res
    return _wrapped

# ---------------- main ----------------
async def main():
    if not CHUTES_API_KEY:
        raise RuntimeError("CHUTES_API_KEY is not set in the environment.")
    # ensure docker image exists (auto-build if missing)
    ensure_docker_image()
    model = await pick_ready_model()

    # One agent with the tools
    runner = AssistantAgent(
        "Runner",
        model_client=model,
        tools=[
            swe_clone,
            swe_install,
            swe_pytest,
            swe_pytest_auto,
            swe_apply_patch_text,
            swe_pytest_full,
            swe_read_file,
            swe_pip_install,
        ],
    )

    # Terminate on any typical pytest tail (pass/fail/error/summary) or cap turns
    # Allow the agent to attempt a fix: only terminate on pass (or cap turns)
    term = (
        TextMentionTermination(" passed in ")
        | TextMentionTermination(" passed")               # e.g., "1 passed, 1 warning"
        | TextMentionTermination(" no tests ran")         # edge case
        | MaxMessageTermination(MAX_TURNS)
    )
    team = RoundRobinGroupChat([runner], termination_condition=term)

    kline = f'-k "{PYTEST_K}"' if PYTEST_K else ""
    # Optional hint from previous attempt to guide this run
    hint_block = ("\n\nPrevious attempt summary (brief):\n" + ATTEMPT_HINT + "\n") if ATTEMPT_HINT else ""
    task = f"""
You are a code-fixing agent working inside a clean Docker container.
Use ONLY the provided tools. Keep outputs minimal.

Steps:
1) swe_clone(repo_url="{TARGET_REPO}", ref="{TARGET_REF}")
2) swe_install()    # installs project and test deps if present
3) Run tests using swe_pytest_auto(pytest_args="-q {kline}".strip()). It will auto-install a missing module if pytest shows ModuleNotFoundError, then re-run tests once. Paste ONLY the returned tail.
4) If tests still fail, get diagnostics using swe_pytest_full(pytest_args="-q -x -vv"). If helpful, open specific files via swe_read_file(path="...").
5) If diagnostics indicate a missing package that was not auto-installed, install it using swe_pip_install(packages="<name>") and re-run tests once via swe_pytest.
6) Attempt EXACTLY ONE minimal unified diff patch (keep it small). Apply via swe_apply_patch_text(diff_text=...). Then re-run tests with swe_pytest and paste ONLY the returned tail. After this second test run, STOP.

CRITICAL OUTPUT RULE:
When you run tests (step 3 or after patch), paste ONLY the exact string returned by swe_pytest (the last non-empty pytest stdout line). No extra words.
{hint_block}"""

    t0 = time.time()
    # initial log record
    if LOG_PATH:
        _log_record({
            "timestamp": _now_iso(),
            "role": "system",
            "content": "run_started",
            "tool_name": None,
            "tool_args": None,
            "tool_result": None,
            "usage": None,
            "run_id": RUN_ID,
            "task_id": TASK_ID,
            "model": MODEL_NAME or getattr(model, "model", None),
            "temperature": MODEL_TEMPERATURE,
            "started_at": _now_iso(),
        })
    # Use streaming UI for consistent console output
    res = await Console(team.run_stream(task=task))
    print(f"\n--- SUMMARY ---\nElapsed seconds: {time.time() - t0:.2f}")
    try:
        print(f"Messages: {len(res.messages)}")
    except Exception:
        pass
    # log terminal tail line as assistant content if detectable via messages
    try:
        for m in getattr(res, "messages", []) or []:
            role = getattr(m, "source", None) or getattr(m, "role", "assistant")
            content = getattr(m, "content", "")
            if isinstance(content, list):
                content = " ".join(str(x) for x in content)
            _log_record({
                "timestamp": _now_iso(),
                "role": str(role),
                "content": _truncate(str(content)),
                "tool_name": None,
                "tool_args": None,
                "tool_result": None,
                "usage": getattr(m, "usage", None),
                "run_id": RUN_ID,
                "task_id": TASK_ID,
                "model": MODEL_NAME or getattr(model, "model", None),
                "temperature": MODEL_TEMPERATURE,
            })
    except Exception:
        pass

if __name__ == "__main__":
    # Kept as a runnable shim; module is also exposed under demas.swe.oneagent
    asyncio.run(main())
