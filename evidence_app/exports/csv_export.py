from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

from ..core.audit import log_action
from .common import EXPORT_FIELDS, build_export_rows


def export_csv(
    con: sqlite3.Connection,
    record_ids: list[int],
    out_path: str | Path,
    *,
    actor: str = "human",
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_export_rows(con, record_ids)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    log_action(
        con, actor=actor, action="export", target_type="export", target_id=None,
        details={"format": "csv", "record_count": len(rows), "out_path": str(out_path)},
    )
    con.commit()
    return out_path
