"""Local-first storage locations. Everything lives under one data dir so the
whole case (originals + database + exports) is a single folder you can back
up, move, or point Time Machine at."""
from __future__ import annotations

import os
from pathlib import Path


def data_dir() -> Path:
    return Path(os.environ.get("EVIDENCE_APP_DATA_DIR", "./data")).resolve()


def db_path() -> Path:
    return data_dir() / "evidence.sqlite3"


def store_root() -> Path:
    return data_dir() / "store"


def export_dir() -> Path:
    return data_dir() / "exports"
