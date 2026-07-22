"""Human review actions: approve AI proposals as-is, or correct them.

Nothing here ever gets called by the AI proposer. `verified` only flips to 1
through these functions, all of which require a human actor.
"""
from __future__ import annotations

import sqlite3

from .audit import log_action, now_iso


def approve_record(con: sqlite3.Connection, record_id: int, *, actor: str = "human") -> None:
    """Accept all of a record's current AI proposals (date, significance,
    entities, tags) as correct, without changing their values."""
    ts = now_iso()
    con.execute(
        "UPDATE records SET review_status = 'approved', reviewed_at = ?, reviewed_by = ?, "
        "record_date_verified = CASE WHEN record_date IS NOT NULL THEN 1 ELSE record_date_verified END, "
        "significance_verified = CASE WHEN significance IS NOT NULL THEN 1 ELSE significance_verified END, "
        "updated_at = ? WHERE id = ?",
        (ts, actor, ts, record_id),
    )
    con.execute("UPDATE record_entities SET verified = 1 WHERE record_id = ?", (record_id,))
    con.execute("UPDATE record_tags SET verified = 1 WHERE record_id = ?", (record_id,))
    con.execute("UPDATE claims SET verified = 1 WHERE record_id = ?", (record_id,))
    log_action(con, actor=actor, action="approve", target_type="record", target_id=record_id)
    con.commit()


def correct_record_date(con: sqlite3.Connection, record_id: int, new_date: str | None, *, actor: str = "human") -> None:
    ts = now_iso()
    con.execute(
        "UPDATE records SET record_date = ?, record_date_proposed_by = 'human', record_date_verified = 1, "
        "review_status = 'corrected', reviewed_at = ?, reviewed_by = ?, updated_at = ? WHERE id = ?",
        (new_date, ts, actor, ts, record_id),
    )
    log_action(
        con, actor=actor, action="correct", target_type="record", target_id=record_id,
        details={"field": "record_date", "new_value": new_date},
    )
    con.commit()


def correct_significance(con: sqlite3.Connection, record_id: int, new_significance: str | None, *, actor: str = "human") -> None:
    ts = now_iso()
    con.execute(
        "UPDATE records SET significance = ?, significance_proposed_by = 'human', significance_verified = 1, "
        "review_status = 'corrected', reviewed_at = ?, reviewed_by = ?, updated_at = ? WHERE id = ?",
        (new_significance, ts, actor, ts, record_id),
    )
    log_action(
        con, actor=actor, action="correct", target_type="record", target_id=record_id,
        details={"field": "significance", "new_value": new_significance},
    )
    con.commit()


def set_entity_verified(con: sqlite3.Connection, record_id: int, entity_id: int, verified: bool, *, actor: str = "human") -> None:
    con.execute(
        "UPDATE record_entities SET verified = ? WHERE record_id = ? AND entity_id = ?",
        (1 if verified else 0, record_id, entity_id),
    )
    log_action(
        con, actor=actor, action="verify_entity" if verified else "reject_entity",
        target_type="record_entity", target_id=record_id, details={"entity_id": entity_id},
    )
    con.commit()


def reject_entity(con: sqlite3.Connection, record_id: int, entity_id: int, *, actor: str = "human") -> None:
    con.execute("DELETE FROM record_entities WHERE record_id = ? AND entity_id = ?", (record_id, entity_id))
    log_action(
        con, actor=actor, action="remove_entity", target_type="record_entity",
        target_id=record_id, details={"entity_id": entity_id},
    )
    con.commit()


def set_tag_verified(con: sqlite3.Connection, record_id: int, tag_id: int, verified: bool, *, actor: str = "human") -> None:
    con.execute(
        "UPDATE record_tags SET verified = ? WHERE record_id = ? AND tag_id = ?",
        (1 if verified else 0, record_id, tag_id),
    )
    log_action(
        con, actor=actor, action="verify_tag" if verified else "reject_tag",
        target_type="record_tag", target_id=record_id, details={"tag_id": tag_id},
    )
    con.commit()


def reject_tag(con: sqlite3.Connection, record_id: int, tag_id: int, *, actor: str = "human") -> None:
    con.execute("DELETE FROM record_tags WHERE record_id = ? AND tag_id = ?", (record_id, tag_id))
    log_action(
        con, actor=actor, action="remove_tag", target_type="record_tag",
        target_id=record_id, details={"tag_id": tag_id},
    )
    con.commit()


def add_human_tag(con: sqlite3.Connection, record_id: int, tag_name: str, *, actor: str = "human") -> int:
    """A tag a human types in directly is verified immediately -- it was
    never a proposal in the first place."""
    row = con.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
    tag_id = row["id"] if row else con.execute("INSERT INTO tags (name) VALUES (?)", (tag_name,)).lastrowid
    con.execute(
        "INSERT INTO record_tags (record_id, tag_id, proposed_by, verified) VALUES (?, ?, 'human', 1) "
        "ON CONFLICT(record_id, tag_id) DO UPDATE SET verified = 1, proposed_by = 'human'",
        (record_id, tag_id),
    )
    log_action(con, actor=actor, action="add_tag", target_type="record_tag", target_id=record_id, details={"tag": tag_name})
    con.commit()
    return tag_id


def add_claim(con: sqlite3.Connection, record_id: int, text: str, *, actor: str = "human", verified: bool = True) -> int:
    cur = con.execute(
        "INSERT INTO claims (record_id, text, proposed_by, verified, created_at) VALUES (?, ?, ?, ?, ?)",
        (record_id, text, "human" if verified else "ai", 1 if verified else 0, now_iso()),
    )
    log_action(con, actor=actor, action="add_claim", target_type="claim", target_id=cur.lastrowid, details={"record_id": record_id})
    con.commit()
    return cur.lastrowid


def link_records(con: sqlite3.Connection, record_id_a: int, record_id_b: int, relation_type: str = "related", note: str | None = None, *, actor: str = "human") -> int:
    a, b = sorted((record_id_a, record_id_b))
    if a == b:
        raise ValueError("cannot link a record to itself")
    cur = con.execute(
        "INSERT OR IGNORE INTO record_links (record_id_a, record_id_b, relation_type, note, created_at, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (a, b, relation_type, note, now_iso(), actor),
    )
    log_action(
        con, actor=actor, action="link_records", target_type="record_link", target_id=cur.lastrowid,
        details={"record_id_a": a, "record_id_b": b, "relation_type": relation_type},
    )
    con.commit()
    return cur.lastrowid
