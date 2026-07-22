"""AI-proposal generation.

This module is a placeholder: it uses cheap regex/heuristics rather than a
real model call, so the vertical slice runs fully offline with no API key.
Every value it writes is stamped `proposed_by='ai'` and `verified=0` and
MUST stay that way until a human approves or corrects it in review --
nothing here is ever allowed to set verified=1.

To swap in a real LLM later: implement a class with the same
`propose(record) -> Proposals` shape as RuleBasedProposer and pass it to
`generate_proposals(con, record_id, proposer=YourProposer())`. The DB layer
doesn't care where proposals came from, only that they arrive unverified.
"""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

from .audit import log_action, now_iso

_DATE_PATTERNS = [
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),                      # 2024-01-02
    re.compile(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b"),                 # 1/2/2024
    re.compile(
        r"\b(\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[a-z]*\s+\d{4})\b",
        re.IGNORECASE,
    ),
]

# Very naive "entity" detector: runs of Title-Case words, 2+ chars, not at
# sentence start punctuation. Good enough to surface *candidates* for human
# review -- it is explicitly not a real NER model.
_ENTITY_RUN = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b")

_STOPWORDS = {"The", "This", "That", "These", "Those", "It", "He", "She", "They", "We", "I"}

DEFAULT_TAG_VOCABULARY = {
    "call": ["call", "phone", "voicemail"],
    "message": ["text", "message", "whatsapp", "sms"],
    "meeting": ["meeting", "met with", "appointment"],
    "financial": ["invoice", "payment", "bank", "£", "$"],
    "medical": ["doctor", "hospital", "clinic", "gp ", "medical"],
    "legal": ["solicitor", "court", "police", "statement", "witness"],
}


@dataclass
class Proposals:
    date: str | None = None
    entities: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    significance: str | None = None


class RuleBasedProposer:
    """Deterministic, offline placeholder for a real AI proposal step."""

    def propose(self, title: str | None, body_text: str) -> Proposals:
        text = body_text or ""
        return Proposals(
            date=self._propose_date(text),
            entities=self._propose_entities(text),
            tags=self._propose_tags(text),
            significance=self._propose_significance(title, text),
        )

    def _propose_date(self, text: str) -> str | None:
        for pattern in _DATE_PATTERNS:
            m = pattern.search(text)
            if m:
                return m.group(1)
        return None

    def _propose_entities(self, text: str) -> list[str]:
        seen: list[str] = []
        for m in _ENTITY_RUN.finditer(text):
            candidate = m.group(1).strip()
            first_word = candidate.split()[0]
            if first_word in _STOPWORDS:
                continue
            if candidate not in seen:
                seen.append(candidate)
            if len(seen) >= 10:
                break
        return seen

    def _propose_tags(self, text: str) -> list[str]:
        lowered = text.lower()
        return [tag for tag, keywords in DEFAULT_TAG_VOCABULARY.items() if any(k in lowered for k in keywords)]

    def _propose_significance(self, title: str | None, text: str) -> str | None:
        stripped = text.strip()
        if not stripped:
            return None
        first_sentence = re.split(r"(?<=[.!?])\s", stripped, maxsplit=1)[0]
        return first_sentence[:280]


def generate_proposals(
    con: sqlite3.Connection,
    record_id: int,
    *,
    proposer: RuleBasedProposer | None = None,
    actor: str = "ai",
) -> Proposals:
    proposer = proposer or RuleBasedProposer()
    row = con.execute("SELECT title, body_text, record_date FROM records WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise ValueError(f"no such record: {record_id}")

    proposals = proposer.propose(row["title"], row["body_text"])

    if proposals.date and not row["record_date"]:
        con.execute(
            "UPDATE records SET record_date = ?, record_date_proposed_by = 'ai', updated_at = ? WHERE id = ?",
            (proposals.date, now_iso(), record_id),
        )

    if proposals.significance:
        con.execute(
            "UPDATE records SET significance = ?, significance_proposed_by = 'ai', updated_at = ? "
            "WHERE id = ? AND significance IS NULL",
            (proposals.significance, now_iso(), record_id),
        )

    for name in proposals.entities:
        entity_id = _get_or_create_entity(con, name)
        con.execute(
            "INSERT OR IGNORE INTO record_entities (record_id, entity_id, proposed_by, verified) "
            "VALUES (?, ?, 'ai', 0)",
            (record_id, entity_id),
        )

    for tag_name in proposals.tags:
        tag_id = _get_or_create_tag(con, tag_name)
        con.execute(
            "INSERT OR IGNORE INTO record_tags (record_id, tag_id, proposed_by, verified) "
            "VALUES (?, ?, 'ai', 0)",
            (record_id, tag_id),
        )

    log_action(
        con,
        actor=actor,
        action="propose",
        target_type="record",
        target_id=record_id,
        details={
            "date": proposals.date,
            "entities": proposals.entities,
            "tags": proposals.tags,
            "has_significance": bool(proposals.significance),
        },
    )
    con.commit()
    return proposals


def _get_or_create_entity(con: sqlite3.Connection, name: str, entity_type: str = "unknown") -> int:
    row = con.execute(
        "SELECT id FROM entities WHERE name = ? AND entity_type = ?", (name, entity_type)
    ).fetchone()
    if row:
        return row["id"]
    cur = con.execute("INSERT INTO entities (name, entity_type) VALUES (?, ?)", (name, entity_type))
    return cur.lastrowid


def _get_or_create_tag(con: sqlite3.Connection, name: str) -> int:
    row = con.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    cur = con.execute("INSERT INTO tags (name) VALUES (?)", (name,))
    return cur.lastrowid
