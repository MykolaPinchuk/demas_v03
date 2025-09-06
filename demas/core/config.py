import os


DOCKER_IMAGE = os.environ.get("SWE_IMAGE", "swebench-lite:py3.10")
WORKDIR = os.path.abspath("sandbox")

# Per-stage timeouts (seconds)
TIMEOUT_CLONE = int(os.environ.get("TIMEOUT_CLONE", "5"))
TIMEOUT_INSTALL = int(os.environ.get("TIMEOUT_INSTALL", "20"))
TIMEOUT_TEST = int(os.environ.get("TIMEOUT_TEST", "5"))


