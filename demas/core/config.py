import os


def _load_local_env() -> None:
    """Load secrets from common local files if present:

    - ~/.config/demas/credentials.env
    - ./.env.local (repo root)
    - ./demas/credentials.txt (repo path you preferred)

    Rules:
    - Lines must be KEY=VALUE (no quoting needed). '#' comments and blank lines ignored.
    - Existing environment variables are NOT overridden.
    """
    # Home credentials
    home_env = os.path.expanduser("~/.config/demas/credentials.env")
    # Repo-local env files
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    local_env = os.path.join(repo_root, ".env.local")
    repo_creds = os.path.join(repo_root, "demas", "credentials.txt")

    for path in (home_env, local_env, repo_creds):
        try:
            if not os.path.isfile(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception:
            # Best-effort; ignore parse errors
            pass


# Load local env before reading defaults
_load_local_env()


DOCKER_IMAGE = os.environ.get("SWE_IMAGE", "swebench-lite:py3.10")
WORKDIR = os.path.abspath("sandbox")

# Per-stage timeouts (seconds)
TIMEOUT_CLONE = int(os.environ.get("TIMEOUT_CLONE", "5"))
TIMEOUT_INSTALL = int(os.environ.get("TIMEOUT_INSTALL", "20"))
TIMEOUT_TEST = int(os.environ.get("TIMEOUT_TEST", "5"))


