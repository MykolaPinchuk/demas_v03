#!/usr/bin/env python3
"""Shim module to preserve imports; logic moved to demas.adapters.swebench."""
from demas.adapters.swebench import map_official_item, load_official_tasks  # re-export

__all__ = ["map_official_item", "load_official_tasks"]

