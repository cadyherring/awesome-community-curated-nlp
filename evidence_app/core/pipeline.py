"""Ties ingest -> parse -> propose into the single entry point the CLI/API use."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from .ingest import ingest_source_file
from .parsers import find_parser
from .proposals import generate_proposals
from .records import create_records_for_source


@dataclass
class FileIngestSummary:
    path: str
    source_file_id: int | None = None
    was_duplicate: bool = False
    parser_used: str | None = None
    records_created: list[int] = field(default_factory=list)
    skipped_reason: str | None = None


def ingest_one_file(
    con: sqlite3.Connection,
    store_root: str | Path,
    path: str | Path,
    *,
    actor: str = "human",
    auto_propose: bool = True,
) -> FileIngestSummary:
    path = Path(path)
    result = ingest_source_file(con, store_root, path, actor=actor)
    summary = FileIngestSummary(path=str(path), source_file_id=result.source_file_id, was_duplicate=not result.created)

    if not result.created:
        return summary  # already ingested + parsed previously; nothing new to do

    source_row = con.execute(
        "SELECT mime_type FROM source_files WHERE id = ?", (result.source_file_id,)
    ).fetchone()
    parser = find_parser(path, source_row["mime_type"])
    if parser is None:
        summary.skipped_reason = "no parser for this file type"
        return summary

    summary.parser_used = parser.name
    con.execute(
        "UPDATE source_files SET parser_name = ?, parser_version = ? WHERE id = ?",
        (parser.name, parser.version, result.source_file_id),
    )
    con.commit()

    parsed = parser.parse(path)
    record_ids = create_records_for_source(con, result.source_file_id, parsed, actor=actor)
    summary.records_created = record_ids

    if auto_propose:
        for record_id in record_ids:
            generate_proposals(con, record_id)

    return summary


def ingest_directory(
    con: sqlite3.Connection,
    store_root: str | Path,
    directory: str | Path,
    *,
    actor: str = "human",
    auto_propose: bool = True,
) -> list[FileIngestSummary]:
    """Ingest every file directly under `directory` (recursive). Intended for
    the small end-to-end vertical slice, not bulk archive import."""
    directory = Path(directory)
    summaries = []
    for path in sorted(directory.rglob("*")):
        if path.is_file():
            summaries.append(ingest_one_file(con, store_root, path, actor=actor, auto_propose=auto_propose))
    return summaries
