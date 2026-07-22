"""Turn ParsedRecord objects into rows, with content-level dedupe."""
from __future__ import annotations

import sqlite3

from .audit import log_action, now_iso
from .hashing import sha256_text
from .parsers import ParsedRecord


def create_records_for_source(
    con: sqlite3.Connection,
    source_file_id: int,
    parsed_records: list[ParsedRecord],
    *,
    actor: str = "human",
) -> list[int]:
    """Insert parsed records, skipping any that exactly duplicate an existing
    record from the same source file (re-running a parser is idempotent)."""
    created_ids: list[int] = []
    ts = now_iso()
    for pr in parsed_records:
        content_hash = sha256_text(pr.body_text)
        existing = con.execute(
            "SELECT id FROM records WHERE source_file_id = ? AND content_sha256 = ?",
            (source_file_id, content_hash),
        ).fetchone()
        if existing is not None:
            continue

        cur = con.execute(
            "INSERT INTO records "
            "(source_file_id, seq_in_source, record_type, title, body_text, content_sha256, "
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                source_file_id,
                pr.seq_in_source,
                pr.record_type,
                pr.title,
                pr.body_text,
                content_hash,
                ts,
                ts,
            ),
        )
        record_id = cur.lastrowid
        created_ids.append(record_id)

        if pr.proposed_date:
            con.execute(
                "UPDATE records SET record_date = ?, record_date_proposed_by = 'ai' WHERE id = ?",
                (pr.proposed_date, record_id),
            )

        log_action(
            con,
            actor=actor,
            action="record_created",
            target_type="record",
            target_id=record_id,
            details={"source_file_id": source_file_id, "record_type": pr.record_type},
        )
    con.commit()
    return created_ids
