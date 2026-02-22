"""Centralised path constants for the hydral project.

All runtime data lives under DATA_ROOT_DIR so that the working directory
of the process does not matter.

Override at runtime via the environment variable DATA_ROOT_DIR:
    export DATA_ROOT_DIR=/mnt/c/hydral
"""
from __future__ import annotations

import os
from pathlib import Path

# ── Root ───────────────────────────────────────────────────────────────────
DATA_ROOT_DIR: Path = Path(os.environ.get("DATA_ROOT_DIR", "/mnt/c/hydral"))

# ── Convenience sub-paths ──────────────────────────────────────────────────
DATA_DIR: Path = DATA_ROOT_DIR / "data"
RAW_DIR: Path = DATA_DIR / "raw"
PROCESSED_DIR: Path = DATA_DIR / "processed"
