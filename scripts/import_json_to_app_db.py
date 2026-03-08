#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db.session import build_database_url, create_engine_from_url, create_session_factory, init_db
from app.services.import_service import ImportService


DEFAULT_TARGET_DB = "apps/api/data/app.db"
MAX_PRINTED_ERRORS = 20


def _parse_trade_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD format") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import returned JSON rows into the application SQLite database.",
    )
    parser.add_argument(
        "-d",
        "--date",
        type=_parse_trade_date,
        default=date.today(),
        help="Trade date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "-f",
        "--file",
        required=True,
        help="Path to the JSON file to import.",
    )
    parser.add_argument(
        "--target-db",
        default=DEFAULT_TARGET_DB,
        help="Path to the target application SQLite database.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    source_path = Path(args.file).expanduser().resolve()
    if not source_path.exists():
        print(f"Import failed: JSON file not found: {source_path}", file=sys.stderr)
        return 1

    target_path = Path(args.target_db).expanduser().resolve()
    engine = create_engine_from_url(build_database_url(target_path))
    init_db(engine)

    session_factory = create_session_factory(engine)
    with session_factory() as session:
        summary = ImportService(session).import_file(
            source_path,
            source_name=source_path.name,
            trade_date_override=args.date,
            ignore_unknown_fields=True,
        )

    engine.dispose()

    if summary.failed_rows:
        print(
            "Import completed with errors: "
            f"trade_date={args.date.isoformat()} "
            f"total_rows={summary.total_rows} "
            f"success_rows={summary.success_rows} "
            f"signal_rows={summary.signal_rows} "
            f"failed_rows={summary.failed_rows} "
            f"batch_id={summary.batch_id} "
            f"target={target_path}",
            file=sys.stderr,
        )
        for error in summary.errors[:MAX_PRINTED_ERRORS]:
            print(
                f"row={error.row_number} message={error.message}",
                file=sys.stderr,
            )
        return 1

    print(
        "Import completed: "
        f"trade_date={args.date.isoformat()} "
        f"total_rows={summary.total_rows} "
        f"success_rows={summary.success_rows} "
        f"signal_rows={summary.signal_rows} "
        f"failed_rows={summary.failed_rows} "
        f"batch_id={summary.batch_id} "
        f"target={target_path}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
