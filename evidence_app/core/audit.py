"""Append-only audit trail. Every mutating action goes through log_action."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log_action(
    con: sqlite3.Connection,
    *,
    actor: str,
    action: str,
    target_type: str,
    target_id: int | None,
    details: dict[str, Any] | None = None,
) -> int:
    cur = con.execute(
        "INSERT INTO audit_log (ts, actor, action, target_type, target_id, details) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (now_iso(), actor, action, target_type, target_id, json.dumps(details or {})),
    )
    return cur.lastrowid
