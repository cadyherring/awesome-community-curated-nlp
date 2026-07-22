"""Shared row-building logic for all export formats.

Every export clearly marks unverified AI proposals -- an exported CSV/XLSX
row is not a place where "AI said so" quietly turns into "fact".
"""
from __future__ import annotations

import sqlite3

from ..core.search import get_record_detail

EXPORT_FIELDS = [
    "id",
    "record_type",
    "title",
    "record_date",
    "record_date_status",
    "significance",
    "significance_status",
    "review_status",
    "tags",
    "entities",
    "source_original_name",
    "source_sha256",
]


def _status(verified: int) -> str:
    return "verified" if verified else "UNVERIFIED (AI proposed)"


def _format_tag(row) -> str:
    marker = "" if row["verified"] else "?"
    return f"{row['name']}{marker}"


def _format_entity(row) -> str:
    marker = "" if row["verified"] else "?"
    return f"{row['name']}{marker}"


def build_export_row(con: sqlite3.Connection, record_id: int) -> dict:
    detail = get_record_detail(con, record_id)
    record = detail["record"]
    source = detail["source"]
    return {
        "id": record["id"],
        "record_type": record["record_type"],
        "title": record["title"] or "",
        "record_date": record["record_date"] or "",
        "record_date_status": _status(record["record_date_verified"]) if record["record_date"] else "",
        "significance": record["significance"] or "",
        "significance_status": _status(record["significance_verified"]) if record["significance"] else "",
        "review_status": record["review_status"],
        "tags": "; ".join(_format_tag(t) for t in detail["tags"]),
        "entities": "; ".join(_format_entity(e) for e in detail["entities"]),
        "source_original_name": source["original_name"] if source else "",
        "source_sha256": source["sha256"] if source else "",
    }


def build_export_rows(con: sqlite3.Connection, record_ids: list[int]) -> list[dict]:
    return [build_export_row(con, rid) for rid in record_ids]
