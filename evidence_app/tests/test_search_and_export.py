import csv

from evidence_app.core.pipeline import ingest_one_file
from evidence_app.core.review import approve_record
from evidence_app.core.search import SearchFilters, search_records
from evidence_app.exports.csv_export import export_csv


def test_fts_search_finds_matching_body_text(con, store_root, sample_dir):
    f1 = sample_dir / "a.txt"
    f1.write_text("The solicitor called about the court hearing.")
    f2 = sample_dir / "b.txt"
    f2.write_text("Grocery list: milk, eggs, bread.")

    ingest_one_file(con, store_root, f1)
    ingest_one_file(con, store_root, f2)

    results = search_records(con, SearchFilters(query="solicitor"))
    assert len(results) == 1
    assert "solicitor" in results[0]["body_text"]


def test_filter_by_review_status(con, store_root, sample_dir):
    f1 = sample_dir / "a.txt"
    f1.write_text("Record one about a meeting.")
    f2 = sample_dir / "b.txt"
    f2.write_text("Record two about a call.")

    r1 = ingest_one_file(con, store_root, f1).records_created[0]
    ingest_one_file(con, store_root, f2)

    approve_record(con, r1)

    unreviewed = search_records(con, SearchFilters(review_status="unreviewed"))
    approved = search_records(con, SearchFilters(review_status="approved"))

    assert len(approved) == 1
    assert approved[0]["id"] == r1
    assert all(r["id"] != r1 for r in unreviewed)


def test_csv_export_marks_unverified_values(con, store_root, sample_dir, tmp_path):
    f = sample_dir / "a.txt"
    f.write_text("Meeting with John Smith on 2024-03-15.")
    record_id = ingest_one_file(con, store_root, f).records_created[0]

    out_path = export_csv(con, [record_id], tmp_path / "out.csv")

    with open(out_path, newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert len(rows) == 1
    row = rows[0]
    assert row["record_date"] == "2024-03-15"
    assert "UNVERIFIED" in row["record_date_status"]

    export_events = con.execute("SELECT COUNT(*) c FROM audit_log WHERE action = 'export'").fetchone()["c"]
    assert export_events == 1


def test_csv_export_shows_verified_after_approval(con, store_root, sample_dir, tmp_path):
    f = sample_dir / "a.txt"
    f.write_text("Meeting with John Smith on 2024-03-15.")
    record_id = ingest_one_file(con, store_root, f).records_created[0]

    approve_record(con, record_id)
    out_path = export_csv(con, [record_id], tmp_path / "out.csv")

    with open(out_path, newline="") as fh:
        row = next(csv.DictReader(fh))

    assert row["record_date_status"] == "verified"
