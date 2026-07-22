# Evidence Management App — vertical slice

A local-first, non-destructive evidence management tool: ingest mixed source
material, preserve originals, hash them, extract metadata, parse into
discrete records, deduplicate, store in SQLite, and review AI-proposed
dates/entities/tags/significance without ever trusting them until a human
approves or corrects them.

This is the **first vertical slice**: a small, real, end-to-end path through
every stage of the pipeline, on `.txt` and `.pdf` files only, before any bulk
archive import. Everything is local — one SQLite file plus a content-addressed
folder of originals, no network calls, no telemetry.

## Why unverified stays unverified

Every AI-proposed value (`record_date`, `significance`, entity links, tag
links) is stored in the *same* row/table as human-confirmed values, with a
`proposed_by` ('ai'/'human') and `verified` (0/1) pair. Nothing ever sets
`verified = 1` except an explicit human action in `core/review.py`. The web
UI renders unverified values in orange with an "UNVERIFIED (AI proposed)"
label, and every CSV/export row carries the same status text — there is no
code path where an AI guess quietly becomes a fact.

The current AI step (`core/proposals.py`) is a deterministic regex/heuristic
placeholder, not a model call, so the slice runs fully offline. Swapping in
a real LLM later means implementing something with the same
`propose(title, body_text) -> Proposals` shape and passing it to
`generate_proposals(..., proposer=YourProposer())` — the DB/UI layer doesn't
care where a proposal came from.

## What's implemented

- **Ingest** (`core/ingest.py`): copies the original into a content-addressed
  store (`<data>/store/objects/<sha256>`), the original file you pointed at
  is never modified. SHA-256 is the identity; re-ingesting identical bytes is
  detected and logged as `ingest_duplicate_skipped` rather than silently
  ignored or silently duplicated.
- **Metadata**: size, mime type, extension, source mtime, ingestion time.
- **Parsing** (`core/parsers.py`): `.txt`/`.md`/`.log` and `.pdf`. Plain text
  becomes one `document` record; text that looks like a timestamped chat/SMS
  export (a common evidence source) is split into one `message` record per
  line, with the timestamp carried through as an unverified proposed date.
  Unrecognised types are skipped (not silently dropped from the DB — logged
  with a reason) rather than guessed at.
- **Record-level dedupe**: identical extracted text within the same source
  file is not inserted twice (`records.content_sha256` UNIQUE).
- **AI proposals** (`core/proposals.py`): heuristic date/entity/tag/
  significance extraction, always unverified.
- **Review** (`core/review.py`): approve-as-is, correct a date/significance
  (which overrides the value AND marks it human-verified), verify/reject
  individual entity or tag proposals, add a human tag (auto-verified, since
  it was never a guess), add a claim, link two records together.
- **Full-text search** (`core/search.py`): SQLite FTS5 over title + body,
  plus filters by tag, entity, review status, and date range.
- **Audit log** (`core/audit.py`): every mutating action anywhere in the app
  writes one row (actor, action, target, timestamp, JSON details).
- **Web UI** (`web/`): FastAPI + a single vanilla-JS page. Two-pane
  list/detail layout. Keyboard: `j`/`k` or arrows to move between records,
  `/` to focus search, `a` to approve all current proposals on the selected
  record, `Esc` to leave a text field.
- **CSV export** (`exports/csv_export.py`): every exported row states
  `verified` or `UNVERIFIED (AI proposed)` per field — the export module is
  a thin `common.py` row-builder plus one file per format, so XLSX/ICS/DOCX/
  PDF are additive, not a rewrite.
- **Timeline data**: `/api/timeline` returns all dated records in
  chronological order (a calendar/timeline *view* on top of this is not
  built yet — see Not yet, below).

## Not yet (by design, for a vertical slice)

- Bulk/recursive import of a full archive (`ingest_directory` exists and is
  used by tests/CLI on small folders, but there's no resumable/parallel bulk
  importer, progress UI, or archive-scale performance work yet).
- Parsers for anything beyond `.txt`/`.md`/`.log`/`.pdf` — no images, audio,
  video, email, WhatsApp `.zip` exports, spreadsheets, etc.
- XLSX, ICS, DOCX, PDF export (CSV only so far; `exports/common.py` is built
  so these are additive).
- A calendar/month-grid UI (the timeline data endpoint exists; no visual
  calendar component yet).
- A graph/visual view of related-record links (links are stored and listed
  per record, no graph view).
- Real AI/LLM-backed proposals (current proposer is a regex heuristic).
- macOS packaging (native shell, code signing, notarization). The core is
  plain Python + SQLite + a local web server so it can be wrapped later
  (e.g. `pywebview`, or a thin Swift/WKWebView shell) without rewriting the
  engine.
- Multi-user auth — this is a single-user, localhost-only tool.

## Running it

```sh
cd evidence_app
pip install -r requirements.txt

# ingest a folder (recursive) of .txt/.pdf files
python -m evidence_app.cli ingest /path/to/small/test/folder

# review in the browser
python -m evidence_app.cli serve --port 8000
# open http://127.0.0.1:8000

# export reviewed records
python -m evidence_app.cli export-csv 1 2 3 --out records.csv
```

Data lives under `./data` by default (`evidence.sqlite3`, `store/` for
originals, `exports/`). Override with `EVIDENCE_APP_DATA_DIR`.

## Tests

```sh
pip install -r requirements.txt
python -m pytest evidence_app/tests -v
```

18 tests cover: hashing + file-level dedupe, plain-text vs. chat-log
parsing, PDF parsing, record-level dedupe, AI proposals starting unverified,
approve/correct/reject review actions, FTS search, status filtering, CSV
export status labelling, and audit log coverage.
