"""Command-line entry points for the vertical slice.

Usage:
    python -m evidence_app.cli ingest <file-or-directory>
    python -m evidence_app.cli serve [--port 8000]
    python -m evidence_app.cli export-csv <record_id> [<record_id> ...] --out FILE
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import config
from .core.db import connect
from .core.pipeline import ingest_directory, ingest_one_file
from .exports.csv_export import export_csv


def cmd_ingest(args: argparse.Namespace) -> None:
    con = connect(config.db_path())
    path = Path(args.path)
    if path.is_dir():
        summaries = ingest_directory(con, config.store_root(), path)
    else:
        summaries = [ingest_one_file(con, config.store_root(), path)]

    for s in summaries:
        if s.was_duplicate:
            status = "duplicate (skipped)"
        elif s.skipped_reason:
            status = f"skipped: {s.skipped_reason}"
        else:
            status = f"{len(s.records_created)} record(s) via {s.parser_used}"
        print(f"{s.path}: {status}")
    con.close()


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    uvicorn.run("evidence_app.web.app:app", host="127.0.0.1", port=args.port, reload=args.reload)


def cmd_export_csv(args: argparse.Namespace) -> None:
    con = connect(config.db_path())
    out_path = export_csv(con, args.record_ids, args.out)
    print(f"wrote {out_path}")
    con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evidence_app")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="ingest a file or a directory of files")
    p_ingest.add_argument("path")
    p_ingest.set_defaults(func=cmd_ingest)

    p_serve = sub.add_parser("serve", help="run the local review web UI")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--reload", action="store_true")
    p_serve.set_defaults(func=cmd_serve)

    p_export = sub.add_parser("export-csv", help="export records to CSV")
    p_export.add_argument("record_ids", type=int, nargs="+")
    p_export.add_argument("--out", default=str(config.export_dir() / "records_export.csv"))
    p_export.set_defaults(func=cmd_export_csv)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
