# team_swebench_oneagent.py
# One-agent MVP for repo validation in Docker with robust termination.
# pip install -U autogen-agentchat autogen-ext[openai]
# docker build -f Dockerfile.swe -t swebench-lite:py3.10 .

import os, shlex, time, asyncio, subprocess
from typing import List, Optional

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.ui import Console

from autogen_core.models import UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient

# ---------------- config ----------------
CHUTES_API_KEY  = os.environ.get("CHUTES_API_KEY")
CHUTES_BASE_URL = os.environ.get("CHUTES_BASE_URL", "https://llm.chutes.ai/v1")

MODEL_CANDIDATES: List[str] = [
    "moonshotai/Kimi-K2-Instruct-75k",
    "openai/gpt-oss-120b",
    "deepseek-ai/DeepSeek-V3-0324",
    "openai/gpt-oss-20b",
]
BASE_MODEL_INFO = {
    "vision": False, "function_calling": True,
    "json_output": False, "structured_output": False, "family": "unknown",
}

DOCKER_IMAGE   = os.environ.get("SWE_IMAGE", "swebench-lite:py3.10")
MAX_TURNS      = 10  # allow diagnostics, install, and one patch attempt

# Per-stage timeouts (seconds), aligned with baseline runner
TIMEOUT_CLONE  = int(os.environ.get("TIMEOUT_CLONE", "5"))
TIMEOUT_INSTALL= int(os.environ.get("TIMEOUT_INSTALL", "20"))
TIMEOUT_TEST   = int(os.environ.get("TIMEOUT_TEST", "5"))
DEPS_DIR      = "/workspace/_deps"  # persisted on host via volume mount

TARGET_REPO = os.environ.get("TARGET_REPO", "https://github.com/pytest-dev/pytest")
TARGET_REF  = os.environ.get("TARGET_REF", "")
PYTEST_K    = os.environ.get("PYTEST_K", "collection")  # example; empty = full run

# ------------- model + preflight -------------
def make_client(model_name: str) -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model=model_name,
        api_key=CHUTES_API_KEY,
        base_url=CHUTES_BASE_URL,
        temperature=0.2,
        include_name_in_message=True,
        model_info=BASE_MODEL_INFO,
    )

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
    for m in MODEL_CANDIDATES:
        c = make_client(m)
        if await preflight(c):
            print(f"[preflight] Using model: {m}")
            return c
        print(f"[preflight] Model not ready: {m} -> next")
    raise RuntimeError("No model available for now.")

# ---------------- docker helpers ----------------
def _docker(cmd: str) -> tuple[int, str, str]:
    workdir = os.path.abspath("sandbox")
    os.makedirs(workdir, exist_ok=True)
    full = f"docker run --rm -v {workdir}:/workspace -w /workspace {DOCKER_IMAGE} bash -lc {shlex.quote(cmd)}"
    p = subprocess.run(full, shell=True, text=True, capture_output=True)
    return p.returncode, p.stdout, p.stderr

# ---- tools (must be async functions with type hints) ----
async def swe_clone(*, repo_url: str, ref: Optional[str] = None) -> str:
    cmds = [
        f"rm -rf project",
        f"timeout {TIMEOUT_CLONE}s git clone --depth 1 {shlex.quote(repo_url)} project",
    ]
    if ref:
        cmds.append(
            f"cd project && timeout {TIMEOUT_CLONE}s git fetch --depth 1 origin {shlex.quote(ref)} && git checkout -q {shlex.quote(ref)}"
        )
    code, out, err = _docker(" && ".join(cmds))
    return "(cloned)" if code == 0 else f"(exit {code})\nSTDOUT:\n{out}\nSTDERR:\n{err}"

async def swe_install(*, req_file: str = "requirements.txt") -> str:
    cmd = (
        "cd project && "
        "python -m pip install -q -U pip && "
        "timeout 10s python -m pip install -q hatchling hatch-vcs meson-python ninja cython || true && "
        f"timeout {TIMEOUT_INSTALL}s python -m pip install -q -e . || true && "
        # If meson build artifacts exist, copy compiled .so into package dir to persist
        "if [ -d build ]; then so=$(find build -name '*_cfinancial*.so' | head -n1); "
        "if [ -n \"$so\" ]; then cp -f \"$so\" numpy_financial/; fi; fi && "
        f"if [ -f {shlex.quote(req_file)} ]; then timeout {TIMEOUT_INSTALL}s python -m pip install -q -r {shlex.quote(req_file)}; else echo 'no requirements.txt'; fi"
    )
    code, out, err = _docker(cmd)
    return (out or "ok").strip() if code == 0 else f"(exit {code})\nSTDOUT:\n{out}\nSTDERR:\n{err}"

async def swe_pytest(*, pytest_args: str = "-q") -> str:
    cmd = (
        f"export PYTHONPATH={DEPS_DIR}:$PYTHONPATH; "
        f"cd project && timeout {TIMEOUT_TEST}s python -m pytest {pytest_args}"
    )
    code, out, err = _docker(cmd)
    # Always return ONLY the last non-empty line of stdout
    last = [ln for ln in (out or "").splitlines() if ln.strip()]
    tail = last[-1] if last else ""
    # Even on failure we just return the tail (so termination can catch it)
    return tail or "(no stdout)"

async def swe_pytest_full(*, pytest_args: str = "-q -x -vv") -> str:
    """Run pytest and return the last ~200 lines of combined stdout+stderr, with ' passed' sanitized
    to avoid triggering termination conditions inadvertently."""
    cmd = (
        f"export PYTHONPATH={DEPS_DIR}:$PYTHONPATH; "
        f"cd project && timeout {TIMEOUT_TEST}s python -m pytest {pytest_args}"
    )
    code, out, err = _docker(cmd)
    text = (out or "") + ("\n" + err if err else "")
    lines = [ln for ln in text.splitlines() if ln is not None]
    tail_block = "\n".join(lines[-200:])
    # sanitize ' passed' phrases to avoid accidental termination
    safe = tail_block.replace(" passed in ", " p✓ssed in ").replace(" passed", " p✓ssed")
    return safe or "(no output)"

async def swe_read_file(*, path: str, max_bytes: int = 20000) -> str:
    """Read a file inside the project (relative path), returning up to max_bytes."""
    rp = shlex.quote(path)
    mb = max(1, int(max_bytes))
    cmd = (
        f"cd project && if [ -f {rp} ]; then head -c {mb} -- {rp}; else echo '(file not found)'; fi"
    )
    code, out, err = _docker(cmd)
    return (out or "(empty)") if code == 0 else f"(exit {code})\nSTDOUT:\n{out}\nSTDERR:\n{err}"

async def swe_pip_install(*, packages: str) -> str:
    """Install one or more packages via pip (space-separated)."""
    pk = packages.strip()
    if not pk:
        return "(no packages)"
    cmd = (
        f"mkdir -p {DEPS_DIR} && "
        f"timeout {TIMEOUT_INSTALL}s python -m pip install -q -t {DEPS_DIR} {shlex.quote(pk)}"
    )
    code, out, err = _docker(cmd)
    return "ok" if code == 0 else f"(exit {code})\nSTDOUT:\n{out}\nSTDERR:\n{err}"
async def swe_apply_patch_text(*, diff_text: str) -> str:
    # Write diff into workspace and apply within the repo
    script = (
        "set -e\n"
        "cd /workspace\n"
        "printf '%s' \"" + diff_text.replace("\\", "\\\\").replace("\"", "\\\"") + "\" > patch.diff\n"
        "cd project\n"
        "timeout 3s git apply /workspace/patch.diff && echo PATCH_APPLIED || (echo PATCH_FAILED >&2; exit 3)\n"
    )
    code, out, err = _docker(script)
    return (out or "").strip() if code == 0 else f"(exit {code})\nSTDOUT:\n{out}\nSTDERR:\n{err}"

# ---------------- main ----------------
async def main():
    if not CHUTES_API_KEY:
        raise RuntimeError("CHUTES_API_KEY is not set in the environment.")
    model = await pick_ready_model()

    # One agent with the tools
    runner = AssistantAgent(
        "Runner",
        model_client=model,
        tools=[swe_clone, swe_install, swe_pytest, swe_apply_patch_text, swe_pytest_full, swe_read_file, swe_pip_install],
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
    task = f"""
You are a code-fixing agent working inside a clean Docker container.
Use ONLY the provided tools. Keep outputs minimal.

Steps:
1) swe_clone(repo_url="{TARGET_REPO}", ref="{TARGET_REF}")
2) swe_install()    # installs project and test deps if present
3) Run tests: swe_pytest(pytest_args="-q {kline}".strip()) and report the tail.
4) If tests fail, get diagnostics using swe_pytest_full(pytest_args="-q -x -vv"). If helpful, open specific files via swe_read_file(path="...").
5) If diagnostics indicate a missing package, install it using swe_pip_install(packages="<name>") and re-run tests once.
6) Attempt EXACTLY ONE minimal unified diff patch (keep it small). Apply via swe_apply_patch_text(diff_text=...). Then re-run tests with swe_pytest and paste ONLY the returned tail. After this second test run, STOP.

CRITICAL OUTPUT RULE:
When you run tests (step 3 or after patch), paste ONLY the exact string returned by swe_pytest (the last non-empty pytest stdout line). No extra words.
"""

    t0 = time.time()
    res = await Console(team.run_stream(task=task))
    print(f"\n--- SUMMARY ---\nElapsed seconds: {time.time() - t0:.2f}")
    try:
        print(f"Messages: {len(res.messages)}")
    except Exception:
        pass

if __name__ == "__main__":
    asyncio.run(main())
