"""Local review UI. Run with: uvicorn evidence_app.web.app:app --reload

Single-user, local-first: one SQLite file, no auth, meant to be reached at
http://127.0.0.1 only.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import config
from ..core import review as review_ops
from ..core.db import connect
from ..core.search import SearchFilters, get_record_detail, search_records
from ..exports.csv_export import export_csv

app = FastAPI(title="Evidence Review")

STATIC_DIR = Path(__file__).with_name("static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def get_db():
    con = connect(config.db_path())
    try:
        yield con
    finally:
        con.close()


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row) if row is not None else None


@app.get("/", response_class=HTMLResponse)
def index():
    return (Path(__file__).with_name("templates") / "index.html").read_text()


@app.get("/api/records")
def api_list_records(
    q: Optional[str] = None,
    tag: Optional[str] = None,
    entity: Optional[str] = None,
    review_status: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    verified_only: bool = False,
    limit: int = 100,
    offset: int = 0,
    con: sqlite3.Connection = Depends(get_db),
):
    filters = SearchFilters(
        query=q, tag=tag, entity=entity, review_status=review_status,
        date_from=date_from, date_to=date_to, verified_only=verified_only,
        limit=limit, offset=offset,
    )
    rows = search_records(con, filters)
    return [row_to_dict(r) for r in rows]


@app.get("/api/timeline")
def api_timeline(con: sqlite3.Connection = Depends(get_db)):
    rows = con.execute(
        "SELECT id, title, record_type, record_date, record_date_verified, review_status "
        "FROM records WHERE record_date IS NOT NULL ORDER BY record_date ASC"
    ).fetchall()
    return [row_to_dict(r) for r in rows]


@app.get("/api/records/{record_id}")
def api_get_record(record_id: int, con: sqlite3.Connection = Depends(get_db)):
    try:
        detail = get_record_detail(con, record_id)
    except ValueError:
        raise HTTPException(404, "record not found")
    return {
        "record": row_to_dict(detail["record"]),
        "source": row_to_dict(detail["source"]),
        "entities": [row_to_dict(r) for r in detail["entities"]],
        "tags": [row_to_dict(r) for r in detail["tags"]],
        "claims": [row_to_dict(r) for r in detail["claims"]],
        "links": [row_to_dict(r) for r in detail["links"]],
    }


@app.post("/api/records/{record_id}/approve")
def api_approve(record_id: int, con: sqlite3.Connection = Depends(get_db)):
    review_ops.approve_record(con, record_id)
    return {"ok": True}


class DateBody(BaseModel):
    value: Optional[str] = None


@app.post("/api/records/{record_id}/date")
def api_set_date(record_id: int, body: DateBody, con: sqlite3.Connection = Depends(get_db)):
    review_ops.correct_record_date(con, record_id, body.value)
    return {"ok": True}


class SignificanceBody(BaseModel):
    value: Optional[str] = None


@app.post("/api/records/{record_id}/significance")
def api_set_significance(record_id: int, body: SignificanceBody, con: sqlite3.Connection = Depends(get_db)):
    review_ops.correct_significance(con, record_id, body.value)
    return {"ok": True}


@app.post("/api/records/{record_id}/tags/{tag_id}/verify")
def api_verify_tag(record_id: int, tag_id: int, con: sqlite3.Connection = Depends(get_db)):
    review_ops.set_tag_verified(con, record_id, tag_id, True)
    return {"ok": True}


@app.post("/api/records/{record_id}/tags/{tag_id}/reject")
def api_reject_tag(record_id: int, tag_id: int, con: sqlite3.Connection = Depends(get_db)):
    review_ops.reject_tag(con, record_id, tag_id)
    return {"ok": True}


@app.post("/api/records/{record_id}/entities/{entity_id}/verify")
def api_verify_entity(record_id: int, entity_id: int, con: sqlite3.Connection = Depends(get_db)):
    review_ops.set_entity_verified(con, record_id, entity_id, True)
    return {"ok": True}


@app.post("/api/records/{record_id}/entities/{entity_id}/reject")
def api_reject_entity(record_id: int, entity_id: int, con: sqlite3.Connection = Depends(get_db)):
    review_ops.reject_entity(con, record_id, entity_id)
    return {"ok": True}


class TagBody(BaseModel):
    name: str


@app.post("/api/records/{record_id}/tags")
def api_add_tag(record_id: int, body: TagBody, con: sqlite3.Connection = Depends(get_db)):
    tag_id = review_ops.add_human_tag(con, record_id, body.name)
    return {"ok": True, "tag_id": tag_id}


class LinkBody(BaseModel):
    other_record_id: int
    relation_type: str = "related"
    note: Optional[str] = None


@app.post("/api/records/{record_id}/links")
def api_link(record_id: int, body: LinkBody, con: sqlite3.Connection = Depends(get_db)):
    try:
        review_ops.link_records(con, record_id, body.other_record_id, body.relation_type, body.note)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


class ExportBody(BaseModel):
    record_ids: list[int]


@app.post("/api/export/csv")
def api_export_csv(body: ExportBody, con: sqlite3.Connection = Depends(get_db)):
    out_path = config.export_dir() / "records_export.csv"
    export_csv(con, body.record_ids, out_path)
    return FileResponse(out_path, filename="records_export.csv", media_type="text/csv")
