"""Parse source files into discrete, reviewable records.

Vertical-slice scope: plain text (with a chat/message-log heuristic so a
WhatsApp-style or timestamped export splits into one record per message
instead of one giant blob) and PDF. Anything else falls back to a single
whole-file record so ingestion never silently drops material -- new parsers
just need to implement the `Parser` protocol and be added to PARSERS.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class ParsedRecord:
    seq_in_source: int
    record_type: str  # 'document' | 'message' | ...
    title: str | None
    body_text: str
    proposed_date: str | None = None  # ISO date/time string, if the parser found one


class Parser(Protocol):
    name: str
    version: str

    def can_parse(self, path: Path, mime_type: str | None) -> bool: ...
    def parse(self, path: Path) -> list[ParsedRecord]: ...


# Matches common chat/message export timestamp prefixes, e.g.:
#   "2024-01-02 10:15 - Alex: hello"
#   "[2024-01-02T10:15:00] Alex: hello"
#   "1/2/24, 10:15 AM - Alex: hello"   (WhatsApp style)
_TIMESTAMP_LINE = re.compile(
    r"""^\s*\[?
    (?P<ts>
        \d{4}-\d{2}-\d{2}[ T]\d{1,2}:\d{2}(:\d{2})?          # ISO-ish
        | \d{1,2}/\d{1,2}/\d{2,4},?\s+\d{1,2}:\d{2}(\s?[AaPp][Mm])?  # D/M/Y, H:MM
    )
    \]?\s*[-,:]?\s*(?P<rest>.*)$""",
    re.VERBOSE,
)


class TextParser:
    name = "text_v1"
    version = "1.0"
    extensions = {".txt", ".md", ".log"}

    def can_parse(self, path: Path, mime_type: str | None) -> bool:
        if path.suffix.lower() in self.extensions:
            return True
        return bool(mime_type and mime_type.startswith("text/"))

    def parse(self, path: Path) -> list[ParsedRecord]:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        non_empty = [ln for ln in lines if ln.strip()]
        matched = [ln for ln in non_empty if _TIMESTAMP_LINE.match(ln)]

        if non_empty and len(matched) / len(non_empty) >= 0.6:
            return self._parse_as_message_log(lines)
        return self._parse_as_document(path, text)

    def _parse_as_document(self, path: Path, text: str) -> list[ParsedRecord]:
        return [
            ParsedRecord(
                seq_in_source=0,
                record_type="document",
                title=path.stem,
                body_text=text,
            )
        ]

    def _parse_as_message_log(self, lines: list[str]) -> list[ParsedRecord]:
        records: list[ParsedRecord] = []
        current: ParsedRecord | None = None
        seq = 0
        for line in lines:
            m = _TIMESTAMP_LINE.match(line)
            if m:
                if current is not None:
                    records.append(current)
                current = ParsedRecord(
                    seq_in_source=seq,
                    record_type="message",
                    title=None,
                    body_text=m.group("rest").strip(),
                    proposed_date=m.group("ts"),
                )
                seq += 1
            elif current is not None and line.strip():
                current.body_text += "\n" + line.strip()
        if current is not None:
            records.append(current)
        return records


class PdfParser:
    name = "pdf_v1"
    version = "1.0"

    def can_parse(self, path: Path, mime_type: str | None) -> bool:
        if path.suffix.lower() == ".pdf":
            return True
        return mime_type == "application/pdf"

    def parse(self, path: Path) -> list[ParsedRecord]:
        from pypdf import PdfReader  # imported lazily so txt-only slices don't need it

        reader = PdfReader(str(path))
        page_texts = [(page.extract_text() or "") for page in reader.pages]
        body = "\n\n".join(page_texts).strip()
        title = f"{path.stem} ({len(reader.pages)} page{'s' if len(reader.pages) != 1 else ''})"
        return [
            ParsedRecord(
                seq_in_source=0,
                record_type="document",
                title=title,
                body_text=body,
            )
        ]


PARSERS: list[Parser] = [TextParser(), PdfParser()]


def find_parser(path: Path, mime_type: str | None) -> Parser | None:
    for parser in PARSERS:
        if parser.can_parse(path, mime_type):
            return parser
    return None
