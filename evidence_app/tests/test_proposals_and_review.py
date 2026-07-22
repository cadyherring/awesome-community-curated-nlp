from evidence_app.core.pipeline import ingest_one_file
from evidence_app.core.review import approve_record, correct_record_date, reject_entity, set_tag_verified
from evidence_app.core.search import get_record_detail


def _ingest_note(con, store_root, sample_dir):
    f = sample_dir / "note.txt"
    f.write_text("Meeting with John Smith on 2024-03-15 about the invoice.")
    summary = ingest_one_file(con, store_root, f)
    return summary.records_created[0]


def test_ai_proposals_start_unverified(con, store_root, sample_dir):
    record_id = _ingest_note(con, store_root, sample_dir)
    detail = get_record_detail(con, record_id)

    record = detail["record"]
    assert record["record_date"] == "2024-03-15"
    assert record["record_date_verified"] == 0
    assert record["record_date_proposed_by"] == "ai"
    assert record["review_status"] == "unreviewed"

    assert len(detail["entities"]) > 0
    assert all(e["verified"] == 0 for e in detail["entities"])
    assert len(detail["tags"]) > 0
    assert all(t["verified"] == 0 for t in detail["tags"])


def test_approve_verifies_everything_unchanged(con, store_root, sample_dir):
    record_id = _ingest_note(con, store_root, sample_dir)
    before = get_record_detail(con, record_id)["record"]["record_date"]

    approve_record(con, record_id)

    detail = get_record_detail(con, record_id)
    assert detail["record"]["record_date"] == before  # value unchanged
    assert detail["record"]["record_date_verified"] == 1
    assert detail["record"]["review_status"] == "approved"
    assert all(e["verified"] == 1 for e in detail["entities"])
    assert all(t["verified"] == 1 for t in detail["tags"])


def test_correct_overrides_value_and_marks_human_verified(con, store_root, sample_dir):
    record_id = _ingest_note(con, store_root, sample_dir)

    correct_record_date(con, record_id, "2024-03-16")

    record = get_record_detail(con, record_id)["record"]
    assert record["record_date"] == "2024-03-16"
    assert record["record_date_verified"] == 1
    assert record["record_date_proposed_by"] == "human"
    assert record["review_status"] == "corrected"


def test_reject_entity_removes_it(con, store_root, sample_dir):
    record_id = _ingest_note(con, store_root, sample_dir)
    entity_id = get_record_detail(con, record_id)["entities"][0]["id"]

    reject_entity(con, record_id, entity_id)

    remaining_ids = [e["id"] for e in get_record_detail(con, record_id)["entities"]]
    assert entity_id not in remaining_ids


def test_verify_single_tag_does_not_verify_others(con, store_root, sample_dir):
    record_id = _ingest_note(con, store_root, sample_dir)
    tags = get_record_detail(con, record_id)["tags"]
    assert len(tags) >= 1
    target = tags[0]

    set_tag_verified(con, record_id, target["id"], True)

    tags_after = {t["id"]: t["verified"] for t in get_record_detail(con, record_id)["tags"]}
    assert tags_after[target["id"]] == 1


def test_every_mutating_action_is_audited(con, store_root, sample_dir):
    record_id = _ingest_note(con, store_root, sample_dir)
    approve_record(con, record_id)

    actions = {row["action"] for row in con.execute("SELECT action FROM audit_log")}
    assert {"ingest", "record_created", "propose", "approve"} <= actions
