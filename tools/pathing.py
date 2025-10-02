# tools/pathing.py
from __future__ import annotations
import os
from pathlib import Path

def exports_dir() -> Path:
    """
    Single source of truth for the project's exports/ folder.

    Priority:
      1) EDGE_FINDER_ROOT env var (explicit project root)
      2) Walk up from this file until we find '<root>/exports'
      3) Fallback to CWD/exports
    """
    env_root = os.environ.get("EDGE_FINDER_ROOT", "").strip()
    if env_root:
        p = Path(env_root) / "exports"
        p.mkdir(parents=True, exist_ok=True)
        return p

    here = Path(__file__).resolve()
    for up in [here.parent] + list(here.parents):
        p = up / "exports"
        if p.exists():
            return p

    p = Path.cwd() / "exports"
    p.mkdir(parents=True, exist_ok=True)
    return p

