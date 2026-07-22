"""Ingest: preserve the original, hash it, extract basic file metadata, dedupe.

Originals are never modified or moved from where the user pointed us — we
copy them into a content-addressed store (`<store_root>/objects/<sha256>`)
and only ever read the copy afterwards. Re-ingesting identical bytes is a
no-op: it's detected by the sha256 UNIQUE constraint on source_files and
recorded in the audit log rather than silently ignored.
"""
from __future__ import annotations

import mimetypes
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .audit import log_action, now_iso
from .hashing import sha256_file


@dataclass
class IngestResult:
    source_file_id: int
    sha256: str
    created: bool  # False if this exact file was already in the store (dedupe)


def _content_addressed_path(store_root: Path, sha256: str, ext: str) -> Path:
    # Two-level fan-out so a large archive doesn't dump millions of files
    # into one directory.
    return store_root / "objects" / sha256[:2] / sha256[2:4] / f"{sha256}{ext}"


def ingest_source_file(
    con: sqlite3.Connection,
    store_root: str | Path,
    original_path: str | Path,
    *,
    actor: str = "human",
) -> IngestResult:
    store_root = Path(store_root)
    original_path = Path(original_path)
    if not original_path.is_file():
        raise FileNotFoundError(original_path)

    sha256 = sha256_file(original_path)

    existing = con.execute(
        "SELECT id FROM source_files WHERE sha256 = ?", (sha256,)
    ).fetchone()
    if existing is not None:
        log_action(
            con,
            actor=actor,
            action="ingest_duplicate_skipped",
            target_type="source_file",
            target_id=existing["id"],
            details={"attempted_path": str(original_path)},
        )
        con.commit()
        return IngestResult(source_file_id=existing["id"], sha256=sha256, created=False)

    ext = original_path.suffix.lower()
    stored_path = _content_addressed_path(store_root, sha256, ext)
    stored_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(original_path, stored_path)  # preserve original; copy is read-only downstream

    stat = original_path.stat()
    mime_type, _ = mimetypes.guess_type(str(original_path))
    source_mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(timespec="seconds")

    cur = con.execute(
        "INSERT INTO source_files "
        "(original_path, original_name, stored_path, sha256, size_bytes, mime_type, "
        " file_ext, ingested_at, source_mtime) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            str(original_path),
            original_path.name,
            str(stored_path),
            sha256,
            stat.st_size,
            mime_type,
            ext,
            now_iso(),
            source_mtime,
        ),
    )
    source_file_id = cur.lastrowid
    log_action(
        con,
        actor=actor,
        action="ingest",
        target_type="source_file",
        target_id=source_file_id,
        details={"original_path": str(original_path), "sha256": sha256, "size_bytes": stat.st_size},
    )
    con.commit()
    return IngestResult(source_file_id=source_file_id, sha256=sha256, created=True)
