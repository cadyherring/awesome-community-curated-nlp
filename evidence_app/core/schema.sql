-- Evidence Management App - core schema
-- Design principle: AI-proposed values live in the SAME row as human-verified
-- values, distinguished only by `proposed_by` + `verified`. Nothing is ever
-- silently promoted to "true" -- the UI/query layer must always be able to
-- tell provisional from confirmed.

PRAGMA foreign_keys = ON;

-- One row per ingested original file. The original bytes are never modified;
-- `stored_path` points at a content-addressed (sha256-named) copy in the
-- evidence store, so re-ingesting the same bytes is a safe no-op (dedupe).
CREATE TABLE IF NOT EXISTS source_files (
    id              INTEGER PRIMARY KEY,
    original_path   TEXT NOT NULL,      -- path as it was found at ingest time
    original_name   TEXT NOT NULL,
    stored_path     TEXT NOT NULL,      -- path inside the content-addressed store
    sha256          TEXT NOT NULL UNIQUE,
    size_bytes      INTEGER NOT NULL,
    mime_type       TEXT,
    file_ext        TEXT,
    ingested_at     TEXT NOT NULL,      -- ISO 8601 UTC
    source_mtime    TEXT,               -- original file's mtime, if known
    parser_name     TEXT,               -- which parser produced records
    parser_version  TEXT
);

-- A discrete, reviewable unit of evidence extracted from a source file.
-- A single source file can yield 1..N records (e.g. one .txt = 1 record,
-- a chat export could later yield many).
CREATE TABLE IF NOT EXISTS records (
    id                      INTEGER PRIMARY KEY,
    source_file_id          INTEGER NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
    seq_in_source           INTEGER NOT NULL DEFAULT 0,  -- order within the source file
    record_type             TEXT NOT NULL,               -- e.g. 'document', 'message'
    title                   TEXT,
    body_text               TEXT NOT NULL DEFAULT '',
    content_sha256          TEXT NOT NULL,                -- hash of body_text, for record-level dedupe

    -- Date of the underlying event/document. AI may propose it; it is not
    -- trusted for chronology/timeline use until record_date_verified = 1.
    record_date             TEXT,
    record_date_proposed_by TEXT CHECK (record_date_proposed_by IN ('ai', 'human')),
    record_date_verified    INTEGER NOT NULL DEFAULT 0,

    significance            TEXT,
    significance_proposed_by TEXT CHECK (significance_proposed_by IN ('ai', 'human')),
    significance_verified   INTEGER NOT NULL DEFAULT 0,

    review_status           TEXT NOT NULL DEFAULT 'unreviewed'
                                 CHECK (review_status IN ('unreviewed', 'approved', 'corrected')),
    reviewed_at             TEXT,
    reviewed_by             TEXT,

    created_at              TEXT NOT NULL,
    updated_at              TEXT NOT NULL,

    UNIQUE (source_file_id, content_sha256)  -- dedupe identical records from same source
);

CREATE INDEX IF NOT EXISTS idx_records_source_file ON records(source_file_id);
CREATE INDEX IF NOT EXISTS idx_records_review_status ON records(review_status);
CREATE INDEX IF NOT EXISTS idx_records_date ON records(record_date);
CREATE INDEX IF NOT EXISTS idx_records_content_hash ON records(content_sha256);

CREATE TABLE IF NOT EXISTS entities (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    entity_type TEXT NOT NULL DEFAULT 'unknown' CHECK (entity_type IN ('person', 'org', 'place', 'unknown')),
    UNIQUE (name, entity_type)
);

CREATE TABLE IF NOT EXISTS record_entities (
    id           INTEGER PRIMARY KEY,
    record_id    INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    entity_id    INTEGER NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    proposed_by  TEXT NOT NULL CHECK (proposed_by IN ('ai', 'human')),
    verified     INTEGER NOT NULL DEFAULT 0,
    UNIQUE (record_id, entity_id)
);

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS record_tags (
    id          INTEGER PRIMARY KEY,
    record_id   INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    proposed_by TEXT NOT NULL CHECK (proposed_by IN ('ai', 'human')),
    verified    INTEGER NOT NULL DEFAULT 0,
    UNIQUE (record_id, tag_id)
);

CREATE TABLE IF NOT EXISTS claims (
    id          INTEGER PRIMARY KEY,
    record_id   INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    text        TEXT NOT NULL,
    proposed_by TEXT NOT NULL CHECK (proposed_by IN ('ai', 'human')),
    verified    INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_claims_record ON claims(record_id);

-- Undirected relationship between two records (e.g. "same incident",
-- "reply to", "corroborates"). Stored once with a_id < b_id to avoid
-- duplicate reverse rows.
CREATE TABLE IF NOT EXISTS record_links (
    id            INTEGER PRIMARY KEY,
    record_id_a   INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    record_id_b   INTEGER NOT NULL REFERENCES records(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL DEFAULT 'related',
    note          TEXT,
    created_at    TEXT NOT NULL,
    created_by    TEXT NOT NULL DEFAULT 'human',
    CHECK (record_id_a < record_id_b),
    UNIQUE (record_id_a, record_id_b, relation_type)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY,
    ts          TEXT NOT NULL,
    actor       TEXT NOT NULL,      -- 'human' / 'ai' / 'system'
    action      TEXT NOT NULL,      -- 'ingest', 'propose', 'approve', 'correct', 'export', ...
    target_type TEXT NOT NULL,      -- 'source_file', 'record', 'entity', ...
    target_id   INTEGER,
    details     TEXT                -- free-form JSON
);

CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_log(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);

-- Full text search over records, kept in sync via triggers below.
CREATE VIRTUAL TABLE IF NOT EXISTS records_fts USING fts5(
    title, body_text, content='records', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS records_ai AFTER INSERT ON records BEGIN
    INSERT INTO records_fts(rowid, title, body_text) VALUES (new.id, new.title, new.body_text);
END;

CREATE TRIGGER IF NOT EXISTS records_ad AFTER DELETE ON records BEGIN
    INSERT INTO records_fts(records_fts, rowid, title, body_text) VALUES ('delete', old.id, old.title, old.body_text);
END;

CREATE TRIGGER IF NOT EXISTS records_au AFTER UPDATE ON records BEGIN
    INSERT INTO records_fts(records_fts, rowid, title, body_text) VALUES ('delete', old.id, old.title, old.body_text);
    INSERT INTO records_fts(rowid, title, body_text) VALUES (new.id, new.title, new.body_text);
END;
