#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.raw_option_record_sync import sync_raw_option_records_to_app_db


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build app.db signal snapshots from raw_option_records.db.",
    )
    parser.add_argument(
        "--source-db",
        default="apps/api/data/raw_option_records.db",
        help="Path to the source raw_option_records SQLite database.",
    )
    parser.add_argument(
        "--target-db",
        default="apps/api/data/app.db",
        help="Path to the target application SQLite database.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        stats = sync_raw_option_records_to_app_db(
            source_db=args.source_db,
            target_db=args.target_db,
        )
    except Exception as exc:
        print(f"Signal sync failed: {exc}", file=sys.stderr)
        return 1

    print(
        "Signal sync completed: "
        f"source_rows={stats.source_row_count} "
        f"parsed={stats.parsed_row_count} "
        f"raw_snapshots={stats.raw_snapshot_count} "
        f"signal_snapshots={stats.signal_snapshot_count} "
        f"skipped={stats.skipped_row_count} "
        f"batch_id={stats.batch_id} "
        f"target={stats.target_db_path}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
