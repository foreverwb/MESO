#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

SOURCE_QUERY = """
SELECT
  rowid AS source_rowid,
  symbol,
  trade_date,
  json_extract(payload, '$.raw_data') AS raw_data
FROM analysis_records
ORDER BY trade_date DESC, symbol ASC;
"""

CREATE_TARGET_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw_option_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_rowid INTEGER NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    trade_date TEXT NOT NULL,
    raw_data_json TEXT NOT NULL,
    imported_at TEXT NOT NULL
);
"""

INSERT_TARGET_ROW_SQL = """
INSERT OR IGNORE INTO raw_option_records (
    source_rowid,
    symbol,
    trade_date,
    raw_data_json,
    imported_at
) VALUES (?, ?, ?, ?, ?);
"""


@dataclass(frozen=True, slots=True)
class ImportStats:
    total_rows: int
    inserted_rows: int
    skipped_rows: int
    duplicate_rows: int


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import raw_data from analysis_records.db into a new SQLite database.",
    )
    parser.add_argument(
        "--source-db",
        required=True,
        help="Path to the source analysis_records SQLite database.",
    )
    parser.add_argument(
        "--target-db",
        required=True,
        help="Path to the target SQLite database to create or update.",
    )
    return parser.parse_args(argv)


def resolve_path(raw_path: str) -> Path:
    return Path(raw_path).expanduser().resolve()


def ensure_target_schema(connection: sqlite3.Connection) -> None:
    connection.execute(CREATE_TARGET_TABLE_SQL)


def normalize_raw_data_json(raw_data: object) -> tuple[str | None, str | None]:
    if raw_data is None:
        return None, "raw_data is null"

    if isinstance(raw_data, str):
        if not raw_data.strip():
            return None, "raw_data is empty"

        try:
            json.loads(raw_data)
        except json.JSONDecodeError as exc:
            return None, f"invalid json: {exc.msg}"

        return raw_data, None

    try:
        normalized_json = json.dumps(raw_data, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        return None, f"raw_data is not JSON serializable: {exc}"

    return normalized_json, None


def import_raw_data(
    source_db: str | Path,
    target_db: str | Path,
    *,
    output_stream: TextIO = sys.stdout,
) -> ImportStats:
    source_path = resolve_path(str(source_db))
    target_path = resolve_path(str(target_db))

    if not source_path.exists():
        raise FileNotFoundError(f"Source database not found: {source_path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    imported_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    total_rows = 0
    inserted_rows = 0
    skipped_rows = 0
    duplicate_rows = 0

    with sqlite3.connect(source_path) as source_connection, sqlite3.connect(target_path) as target_connection:
        source_connection.row_factory = sqlite3.Row
        ensure_target_schema(target_connection)

        for row in source_connection.execute(SOURCE_QUERY):
            total_rows += 1
            raw_data_json, skip_reason = normalize_raw_data_json(row["raw_data"])

            if skip_reason is not None:
                skipped_rows += 1
                print(
                    "Skipping "
                    f"source_rowid={row['source_rowid']} "
                    f"symbol={row['symbol']} "
                    f"trade_date={row['trade_date']}: "
                    f"{skip_reason}",
                    file=output_stream,
                )
                continue

            cursor = target_connection.execute(
                INSERT_TARGET_ROW_SQL,
                (
                    row["source_rowid"],
                    row["symbol"],
                    row["trade_date"],
                    raw_data_json,
                    imported_at,
                ),
            )

            if cursor.rowcount == 0:
                duplicate_rows += 1
                continue

            inserted_rows += 1

        target_connection.commit()

    print(
        "Import completed: "
        f"total={total_rows} "
        f"inserted={inserted_rows} "
        f"skipped={skipped_rows} "
        f"duplicates={duplicate_rows} "
        f"target={target_path}",
        file=output_stream,
    )

    return ImportStats(
        total_rows=total_rows,
        inserted_rows=inserted_rows,
        skipped_rows=skipped_rows,
        duplicate_rows=duplicate_rows,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        import_raw_data(args.source_db, args.target_db)
    except (FileNotFoundError, sqlite3.Error) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
