#!/usr/bin/env python3
"""
SWE-bench adapter: load an "official"-style JSONL and map records into our local schema.

Input expectations per record (flexible; aliases supported):
- repo or repo_url: string (required)
- ref or commit: string (required)
- pytest_k or test: string (optional)
- diff or patch_b64: either unified diff text (we will base64-encode) or base64-encoded diff already
- timeouts: { clone, install, test } (optional)

Other fields are passed through unchanged.

Each mapped record will include at minimum: task_id, repo, ref, pytest_k, patch_b64, timeouts.
If task_id is missing, it is synthesized as "<repo_name>_<ref7>".
"""
import os
import json
import base64
from typing import Dict, Any, List


def _b64_from_diff_or_b64(val: str) -> str:
    if not val:
        return ""
    # Heuristics: if it looks like a unified diff header, encode; otherwise assume already b64
    if val.lstrip().startswith("diff ") or val.lstrip().startswith("--- ") or "\n+++ " in val:
        return base64.b64encode(val.encode("utf-8")).decode("ascii")
    # try to decode as b64; if fails, encode as plain text
    try:
        base64.b64decode(val.encode("ascii"))
        return val
    except Exception:
        return base64.b64encode(val.encode("utf-8")).decode("ascii")


def map_official_item(item: Dict[str, Any]) -> Dict[str, Any]:
    repo = item.get("repo") or item.get("repo_url") or ""
    ref = item.get("ref") or item.get("commit") or ""
    pytest_k = item.get("pytest_k") or item.get("test") or ""
    patch_b64 = item.get("patch_b64") or _b64_from_diff_or_b64(item.get("diff", ""))
    timeouts = item.get("timeouts") or {}
    # synthesize task_id if missing
    task_id = item.get("task_id")
    if not task_id:
        repo_name = repo.rstrip("/").split("/")[-1] if repo else "repo"
        ref7 = (ref or "HEAD")[:7]
        task_id = f"{repo_name}_{ref7}"
    mapped: Dict[str, Any] = {
        "task_id": task_id,
        "repo": repo,
        "ref": ref,
        "pytest_k": pytest_k,
        "patch_b64": patch_b64,
        "timeouts": timeouts,
    }
    # pass through extras
    for k, v in item.items():
        if k not in mapped:
            mapped[k] = v
    return mapped


def load_official_tasks(path: str) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            tasks.append(map_official_item(rec))
    return tasks


