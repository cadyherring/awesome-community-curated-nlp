from evidence_app.core.hashing import sha256_file
from evidence_app.core.ingest import ingest_source_file


def test_ingest_preserves_original_and_hashes(con, store_root, sample_dir):
    f = sample_dir / "a.txt"
    f.write_text("hello world")

    result = ingest_source_file(con, store_root, f)

    assert result.created is True
    assert result.sha256 == sha256_file(f)
    assert f.exists() and f.read_text() == "hello world"  # original untouched

    row = con.execute("SELECT * FROM source_files WHERE id = ?", (result.source_file_id,)).fetchone()
    assert row["sha256"] == result.sha256
    from pathlib import Path
    assert Path(row["stored_path"]).exists()
    assert Path(row["stored_path"]).read_text() == "hello world"


def test_ingest_dedupes_identical_bytes(con, store_root, sample_dir):
    f1 = sample_dir / "a.txt"
    f1.write_text("same content")
    f2 = sample_dir / "b.txt"
    f2.write_text("same content")

    r1 = ingest_source_file(con, store_root, f1)
    r2 = ingest_source_file(con, store_root, f2)

    assert r1.created is True
    assert r2.created is False
    assert r1.source_file_id == r2.source_file_id

    count = con.execute("SELECT COUNT(*) c FROM source_files").fetchone()["c"]
    assert count == 1

    dup_events = con.execute(
        "SELECT COUNT(*) c FROM audit_log WHERE action = 'ingest_duplicate_skipped'"
    ).fetchone()["c"]
    assert dup_events == 1


def test_different_content_is_not_deduped(con, store_root, sample_dir):
    f1 = sample_dir / "a.txt"
    f1.write_text("content one")
    f2 = sample_dir / "b.txt"
    f2.write_text("content two")

    r1 = ingest_source_file(con, store_root, f1)
    r2 = ingest_source_file(con, store_root, f2)

    assert r1.created is True
    assert r2.created is True
    assert r1.source_file_id != r2.source_file_id
