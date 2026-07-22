from pathlib import Path

from evidence_app.core.parsers import find_parser


def test_plain_document_becomes_one_record(sample_dir):
    f = sample_dir / "note.txt"
    f.write_text("Just a normal paragraph of notes.\nSecond line.")

    parser = find_parser(f, "text/plain")
    records = parser.parse(f)

    assert len(records) == 1
    assert records[0].record_type == "document"
    assert "Just a normal paragraph" in records[0].body_text


def test_chat_log_splits_into_message_records(sample_dir):
    f = sample_dir / "chat.txt"
    f.write_text(
        "2024-01-02 10:00 - Alex: hi\n"
        "2024-01-02 10:01 - Sam: hello there\n"
        "2024-01-02 10:02 - Alex: how are you\n"
    )

    parser = find_parser(f, "text/plain")
    records = parser.parse(f)

    assert len(records) == 3
    assert all(r.record_type == "message" for r in records)
    assert records[0].proposed_date == "2024-01-02 10:00"
    assert records[0].body_text == "Alex: hi"


def test_chat_log_continuation_lines_are_appended(sample_dir):
    f = sample_dir / "chat.txt"
    f.write_text(
        "2024-01-02 10:00 - Alex: hi\n"
        "this continues the same message\n"
        "2024-01-02 10:01 - Sam: hello\n"
    )

    parser = find_parser(f, "text/plain")
    records = parser.parse(f)

    assert len(records) == 2
    assert "continues the same message" in records[0].body_text


def test_pdf_parses_to_one_record(sample_dir):
    reportlab_canvas = _make_test_pdf(sample_dir / "doc.pdf")
    parser = find_parser(reportlab_canvas, "application/pdf")
    records = parser.parse(reportlab_canvas)

    assert len(records) == 1
    assert records[0].record_type == "document"
    assert "Hello PDF evidence" in records[0].body_text


def _make_test_pdf(path: Path) -> Path:
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path))
    c.drawString(72, 720, "Hello PDF evidence")
    c.save()
    return path


def test_unsupported_extension_has_no_parser(sample_dir):
    f = sample_dir / "image.jpg"
    f.write_bytes(b"\xff\xd8\xff\xe0fakejpegbytes")

    parser = find_parser(f, "image/jpeg")
    assert parser is None
