import os
import shlex
import subprocess
from typing import Optional, Tuple


def run_docker_bash(cmd: str, *, image: Optional[str] = None, workdir: Optional[str] = None, timeout: Optional[int] = None) -> Tuple[int, str, str]:
    """Run a shell command inside a transient Docker container.

    - Mounts the host `workdir` to /workspace and sets it as the working dir
    - Uses the provided Docker image
    - Returns (exit_code, stdout, stderr)
    - If a timeout is provided, caps the entire container run
    """
    img = image or os.environ.get("SWE_IMAGE", "swebench-lite:py3.10")
    wd = os.path.abspath(workdir or "sandbox")
    os.makedirs(wd, exist_ok=True)
    docker_cmd = f"docker run --rm -v {wd}:/workspace -w /workspace {img} bash -lc {shlex.quote(cmd)}"
    try:
        p = subprocess.run(
            docker_cmd,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout if timeout and timeout > 0 else None,
        )
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        return 124, e.stdout or "", e.stderr or ""


