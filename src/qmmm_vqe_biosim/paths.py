from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    """Return repository root folder."""
    return Path(__file__).resolve().parents[2]


def data_root() -> Path:
    """
    Data root (gitignored). Override with QMMM_VQE_BIOSIM_DATA_DIR if desired.
    Default: <repo>/data
    """
    default = repo_root() / "data"
    return Path(os.environ.get("QMMM_VQE_BIOSIM_DATA_DIR", str(default))).resolve()


def ensure_project_dirs() -> dict[str, Path]:
    """
    Create expected project directories (safe if they already exist).
    Note: data/ and results/ are gitignored.
    """
    root = repo_root()
    droot = data_root()

    dirs = {
        "repo": root,
        "data": droot,
        "raw": droot / "raw",
        "processed": droot / "processed",
        "results": root / "results",
    }
    for p in dirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return dirs
