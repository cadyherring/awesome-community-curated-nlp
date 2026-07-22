"""Full-text search + filtering over records."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class SearchFilters:
    query: str | None = None          # FTS5 match expression against title/body
    tag: str | None = None
    entity: str | None = None
    review_status: str | None = None  # 'unreviewed' | 'approved' | 'corrected'
    date_from: str | None = None      # inclusive, ISO date string
    date_to: str | None = None        # inclusive, ISO date string
    verified_only: bool = False       # only records with record_date_verified = 1
    limit: int = 100
    offset: int = 0


def search_records(con: sqlite3.Connection, filters: SearchFilters) -> list[sqlite3.Row]:
    joins = []
    where = []
    params: list = []

    base = "SELECT DISTINCT r.* FROM records r"

    if filters.query:
        joins.append("JOIN records_fts fts ON fts.rowid = r.id")
        where.append("records_fts MATCH ?")
        params.append(filters.query)

    if filters.tag:
        joins.append("JOIN record_tags rt ON rt.record_id = r.id JOIN tags t ON t.id = rt.tag_id")
        where.append("t.name = ?")
        params.append(filters.tag)

    if filters.entity:
        joins.append("JOIN record_entities re ON re.record_id = r.id JOIN entities e ON e.id = re.entity_id")
        where.append("e.name = ?")
        params.append(filters.entity)

    if filters.review_status:
        where.append("r.review_status = ?")
        params.append(filters.review_status)

    if filters.date_from:
        where.append("r.record_date >= ?")
        params.append(filters.date_from)

    if filters.date_to:
        where.append("r.record_date <= ?")
        params.append(filters.date_to)

    if filters.verified_only:
        where.append("r.record_date_verified = 1")

    sql = base + (" " + " ".join(joins) if joins else "")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY r.record_date IS NULL, r.record_date ASC, r.id ASC LIMIT ? OFFSET ?"
    params.extend([filters.limit, filters.offset])

    return con.execute(sql, params).fetchall()


def get_record_detail(con: sqlite3.Connection, record_id: int) -> dict:
    record = con.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
    if record is None:
        raise ValueError(f"no such record: {record_id}")

    source = con.execute("SELECT * FROM source_files WHERE id = ?", (record["source_file_id"],)).fetchone()
    entities = con.execute(
        "SELECT e.id, e.name, e.entity_type, re.proposed_by, re.verified "
        "FROM record_entities re JOIN entities e ON e.id = re.entity_id WHERE re.record_id = ?",
        (record_id,),
    ).fetchall()
    tags = con.execute(
        "SELECT t.id, t.name, rt.proposed_by, rt.verified "
        "FROM record_tags rt JOIN tags t ON t.id = rt.tag_id WHERE rt.record_id = ?",
        (record_id,),
    ).fetchall()
    claims = con.execute("SELECT * FROM claims WHERE record_id = ?", (record_id,)).fetchall()
    links = con.execute(
        "SELECT * FROM record_links WHERE record_id_a = ? OR record_id_b = ?", (record_id, record_id)
    ).fetchall()

    return {
        "record": record,
        "source": source,
        "entities": entities,
        "tags": tags,
        "claims": claims,
        "links": links,
    }
