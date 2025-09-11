import json
from typing import List, Dict, Any, Tuple


def load_seed_tasks(path: str) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    seen_ids = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            tid = rec.get("task_id")
            if tid and tid in seen_ids:
                continue
            if tid:
                seen_ids.add(tid)
            tasks.append(rec)
    return tasks


def extract_pytest_tail(stdout: str, stderr: str) -> str:
    """Return the most reliable pytest summary tail line from outputs.

    Preference order:
    1) A line containing " passed" without " failed"/" error" if present
    2) Otherwise, the last non-empty stdout line
    3) Otherwise, the last non-empty stderr line
    4) Fallback: "(no output)"
    """
    try:
        combined = (stdout or "") + ("\n" + stderr if stderr else "")
        # First, search for a pytest summary-like line reliably indicating pass
        for ln in reversed([ln.strip() for ln in combined.splitlines() if ln.strip()]):
            if (" passed" in ln) and (" failed" not in ln) and (" error" not in ln):
                return ln
        # Next, last non-empty stdout line
        for ln in reversed([ln.strip() for ln in (stdout or "").splitlines() if ln.strip()]):
            return ln
        # Next, last non-empty stderr line
        for ln in reversed([ln.strip() for ln in (stderr or "").splitlines() if ln.strip()]):
            return ln
    except Exception:
        pass
    return "(no output)"

