from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
import json
import sqlite3
from pathlib import Path
from typing import Any

from app.core.enums import EarningsRegime, ProbabilityTier, Quadrant, SignalLabel
from app.core.settings import settings
from app.db.session import DEFAULT_DATABASE_FILENAME, build_database_url, create_engine_from_url, create_session_factory, init_db
from app.repositories.batches import BatchCreate, BatchRepository
from app.repositories.raw_snapshots import RawSnapshotCreate, RawSnapshotRepository
from app.repositories.signal_snapshots import SignalSnapshotCreate, SignalSnapshotRepository
from app.schemas.history_schema import HistorySignalRecord
from app.services.classifier import ClassifiedSignalRecord, SignalClassifier
from app.services.cross_section_ranker import CrossSectionRanker
from app.services.feature_engine import FeatureEngine
from app.services.shift_engine import ShiftEngine
from app.services.scoring_engine import ScoringEngine
from app.testing.analysis_records import ParsedRawDataRecord
from app.testing.feature_scoring import build_feature_scoring_source, parse_mixed_numeric


SOURCE_QUERY = """
SELECT
  source_rowid,
  symbol,
  trade_date,
  raw_data_json
FROM raw_option_records
ORDER BY trade_date DESC, symbol ASC, source_rowid ASC;
"""

MONTH_LOOKUP = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}

MAX_SUMMARY_ISSUES = 20


@dataclass(frozen=True, slots=True)
class RawOptionRecordSourceRow:
    source_rowid: int
    symbol: str
    trade_date: str
    raw_data_json: str


@dataclass(frozen=True, slots=True)
class SyncIssue:
    source_rowid: int
    symbol: str
    trade_date: str
    stage: str
    reason: str


@dataclass(frozen=True, slots=True)
class PreparedSyncRecord:
    source_rowid: int
    symbol: str
    trade_date: date
    raw_data: dict[str, Any]
    raw_snapshot: RawSnapshotCreate
    scoring_input: dict[str, Any]
    event_status: str


@dataclass(frozen=True, slots=True)
class ClassifiedSyncRecord:
    source_rowid: int
    classified: ClassifiedSignalRecord


@dataclass(frozen=True, slots=True)
class RawOptionRecordSyncStats:
    source_row_count: int
    parsed_row_count: int
    raw_snapshot_count: int
    signal_snapshot_count: int
    skipped_row_count: int
    batch_id: int
    target_db_path: Path
    issues: tuple[SyncIssue, ...]


def sync_raw_option_records_to_app_db(
    source_db: str | Path,
    target_db: str | Path | None = None,
    *,
    source_name: str | None = None,
) -> RawOptionRecordSyncStats:
    source_path = Path(source_db).expanduser().resolve()
    target_path = _resolve_target_path(target_db)

    if not source_path.exists():
        raise FileNotFoundError(f"raw_option_records database not found: {source_path}")

    source_rows = _fetch_source_rows(source_path)
    feature_engine = FeatureEngine()
    cross_section_ranker = CrossSectionRanker()
    scoring_engine = ScoringEngine()
    classifier = SignalClassifier()
    shift_engine = ShiftEngine()

    engine = create_engine_from_url(build_database_url(target_path))
    init_db(engine)
    session_factory = create_session_factory(engine)

    issues: list[SyncIssue] = []

    with session_factory() as session:
        batch = BatchRepository(session).create_batch(
            BatchCreate(
                source_name=source_name or source_path.name,
                source_type="raw_option_records_sqlite",
                import_started_at=_utcnow(),
                status="running",
                summary_json={},
            ),
        )
        session.flush()

        prepared_records = _prepare_records(
            source_rows,
            batch_id=batch.id,
            issues=issues,
            feature_engine=feature_engine,
        )
        raw_rows = [record.raw_snapshot for record in prepared_records]
        ranked_inputs = cross_section_ranker.rank_records(
            [record.scoring_input for record in prepared_records],
        )
        classified_records = _classify_records(
            prepared_records,
            ranked_inputs,
            issues=issues,
            scoring_engine=scoring_engine,
            classifier=classifier,
        )
        shift_flags = _compute_shift_flags(classified_records, shift_engine=shift_engine)
        signal_rows = _build_signal_rows(
            classified_records,
            batch_id=batch.id,
            shift_flags=shift_flags,
        )

        if raw_rows:
            RawSnapshotRepository(session).insert_raw_rows(raw_rows)
        if signal_rows:
            SignalSnapshotRepository(session).insert_signal_rows(signal_rows)

        batch.import_finished_at = _utcnow()
        batch.total_rows = len(source_rows)
        batch.success_rows = len(signal_rows)
        batch.failed_rows = len(issues)
        batch.status = "completed" if not issues else "completed_with_errors"
        batch.summary_json = {
            "source_row_count": len(source_rows),
            "parsed_row_count": len(prepared_records),
            "raw_snapshot_count": len(raw_rows),
            "signal_snapshot_count": len(signal_rows),
            "skipped_row_count": len(issues),
            "issue_samples": [
                {
                    "source_rowid": issue.source_rowid,
                    "symbol": issue.symbol,
                    "trade_date": issue.trade_date,
                    "stage": issue.stage,
                    "reason": issue.reason,
                }
                for issue in issues[:MAX_SUMMARY_ISSUES]
            ],
        }
        session.commit()

        return RawOptionRecordSyncStats(
            source_row_count=len(source_rows),
            parsed_row_count=len(prepared_records),
            raw_snapshot_count=len(raw_rows),
            signal_snapshot_count=len(signal_rows),
            skipped_row_count=len(issues),
            batch_id=batch.id,
            target_db_path=target_path,
            issues=tuple(issues),
        )


def _fetch_source_rows(source_path: Path) -> list[RawOptionRecordSourceRow]:
    with sqlite3.connect(source_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(SOURCE_QUERY).fetchall()

    return [
        RawOptionRecordSourceRow(
            source_rowid=row["source_rowid"],
            symbol=row["symbol"],
            trade_date=row["trade_date"],
            raw_data_json=row["raw_data_json"],
        )
        for row in rows
    ]


def _prepare_records(
    source_rows: list[RawOptionRecordSourceRow],
    *,
    batch_id: int,
    issues: list[SyncIssue],
    feature_engine: FeatureEngine,
) -> list[PreparedSyncRecord]:
    prepared_records: list[PreparedSyncRecord] = []
    seen_keys: set[tuple[date, str]] = set()

    for row in source_rows:
        try:
            trade_date = date.fromisoformat(row.trade_date)
        except ValueError:
            issues.append(
                SyncIssue(
                    source_rowid=row.source_rowid,
                    symbol=row.symbol,
                    trade_date=row.trade_date,
                    stage="trade_date",
                    reason=f"trade_date is not ISO-8601 parseable: {row.trade_date!r}",
                ),
            )
            continue

        dedupe_key = (trade_date, row.symbol.upper())
        if dedupe_key in seen_keys:
            issues.append(
                SyncIssue(
                    source_rowid=row.source_rowid,
                    symbol=row.symbol,
                    trade_date=row.trade_date,
                    stage="dedupe",
                    reason="duplicate symbol/trade_date row was skipped",
                ),
            )
            continue
        seen_keys.add(dedupe_key)

        try:
            raw_payload = json.loads(row.raw_data_json)
        except json.JSONDecodeError as exc:
            issues.append(
                SyncIssue(
                    source_rowid=row.source_rowid,
                    symbol=row.symbol,
                    trade_date=row.trade_date,
                    stage="raw_data_json",
                    reason=f"invalid json: {exc.msg}",
                ),
            )
            continue

        if not isinstance(raw_payload, dict):
            issues.append(
                SyncIssue(
                    source_rowid=row.source_rowid,
                    symbol=row.symbol,
                    trade_date=row.trade_date,
                    stage="raw_data_json",
                    reason=f"raw_data_json must be an object, got {type(raw_payload).__name__}",
                ),
            )
            continue

        parsed_record = ParsedRawDataRecord(
            symbol=row.symbol,
            trade_date=trade_date.isoformat(),
            raw_data=raw_payload,
        )

        scoring_source = build_feature_scoring_source(parsed_record)
        scoring_source["trade_date"] = trade_date
        scoring_source["symbol"] = row.symbol
        scoring_source["batch_id"] = batch_id

        try:
            feature_record = feature_engine.build_feature_record(scoring_source)
        except Exception as exc:
            issues.append(
                SyncIssue(
                    source_rowid=row.source_rowid,
                    symbol=row.symbol,
                    trade_date=row.trade_date,
                    stage="feature",
                    reason=str(exc),
                ),
            )
            continue

        prepared_records.append(
            PreparedSyncRecord(
                source_rowid=row.source_rowid,
                symbol=row.symbol,
                trade_date=trade_date,
                raw_data=raw_payload,
                raw_snapshot=_build_raw_snapshot(
                    symbol=row.symbol,
                    trade_date=trade_date,
                    raw_data=raw_payload,
                    batch_id=batch_id,
                ),
                scoring_input=scoring_source | feature_record.model_dump(mode="python"),
                event_status=_resolve_event_status(raw_payload.get("Earnings"), trade_date),
            ),
        )

    return prepared_records


def _classify_records(
    prepared_records: list[PreparedSyncRecord],
    ranked_inputs: list[dict[str, Any]],
    *,
    issues: list[SyncIssue],
    scoring_engine: ScoringEngine,
    classifier: SignalClassifier,
) -> list[ClassifiedSyncRecord]:
    classified_records: list[ClassifiedSyncRecord] = []

    for prepared_record, ranked_input in zip(prepared_records, ranked_inputs, strict=True):
        try:
            scoring_record = scoring_engine.score_all(ranked_input)
            classified = classifier.classify(
                scoring_record,
                event_status=prepared_record.event_status,
            )
        except Exception as exc:
            issues.append(
                SyncIssue(
                    source_rowid=prepared_record.source_rowid,
                    symbol=prepared_record.symbol,
                    trade_date=prepared_record.trade_date.isoformat(),
                    stage="signal",
                    reason=str(exc),
                ),
            )
            continue

        classified_records.append(
            ClassifiedSyncRecord(
                source_rowid=prepared_record.source_rowid,
                classified=classified,
            ),
        )

    return classified_records


def _compute_shift_flags(
    classified_records: list[ClassifiedSyncRecord],
    *,
    shift_engine: ShiftEngine,
) -> dict[tuple[str, date], bool]:
    grouped_records: dict[str, list[HistorySignalRecord]] = defaultdict(list)
    shift_flags: dict[tuple[str, date], bool] = {}

    for record in classified_records:
        classified = record.classified
        grouped_records[classified.symbol].append(
            HistorySignalRecord(
                trade_date=classified.trade_date,
                symbol=classified.symbol,
                batch_id=classified.batch_id or 0,
                s_dir=classified.s_dir,
                s_vol=classified.s_vol,
                s_conf=classified.s_conf,
                s_pers=classified.s_pers,
                quadrant=classified.quadrant,
                signal_label=classified.signal_label,
                event_regime=classified.event_regime,
                prob_tier=classified.prob_tier,
                is_watchlist=classified.is_watchlist,
            ),
        )

    for symbol, records in grouped_records.items():
        evaluated_records = shift_engine.evaluate(records)
        for evaluated_record in evaluated_records:
            shift_flags[(symbol, evaluated_record.trade_date)] = evaluated_record.shift_state != "none"

    return shift_flags


def _build_signal_rows(
    classified_records: list[ClassifiedSyncRecord],
    *,
    batch_id: int,
    shift_flags: dict[tuple[str, date], bool],
) -> list[SignalSnapshotCreate]:
    rows: list[SignalSnapshotCreate] = []

    for record in classified_records:
        classified = record.classified
        rows.append(
            SignalSnapshotCreate(
                trade_date=classified.trade_date,
                symbol=classified.symbol,
                s_dir=classified.s_dir,
                s_vol=classified.s_vol,
                s_conf=classified.s_conf,
                s_pers=classified.s_pers,
                quadrant=Quadrant(classified.quadrant),
                signal_label=SignalLabel(classified.signal_label),
                event_regime=EarningsRegime(classified.event_regime),
                shift_flag=shift_flags.get((classified.symbol, classified.trade_date), False),
                prob_tier=_to_probability_tier(classified.prob_tier),
                is_watchlist=classified.is_watchlist,
                batch_id=batch_id,
            ),
        )

    return rows


def _build_raw_snapshot(
    *,
    symbol: str,
    trade_date: date,
    raw_data: dict[str, Any],
    batch_id: int,
) -> RawSnapshotCreate:
    return RawSnapshotCreate(
        trade_date=trade_date,
        symbol=symbol,
        raw_payload_json=raw_data,
        rel_vol_to_90d=parse_mixed_numeric(raw_data.get("RelVolTo90D")),
        call_volume=_coerce_int(raw_data.get("CallVolume")),
        put_volume=_coerce_int(raw_data.get("PutVolume")),
        put_pct=parse_mixed_numeric(raw_data.get("PutPct")),
        single_leg_pct=parse_mixed_numeric(raw_data.get("SingleLegPct")),
        multi_leg_pct=parse_mixed_numeric(raw_data.get("MultiLegPct")),
        contingent_pct=parse_mixed_numeric(raw_data.get("ContingentPct")),
        rel_notional_to_90d=parse_mixed_numeric(raw_data.get("RelNotionalTo90D")),
        call_notional=parse_mixed_numeric(raw_data.get("CallNotional")),
        put_notional=parse_mixed_numeric(raw_data.get("PutNotional")),
        iv30_chg_pct=parse_mixed_numeric(raw_data.get("IV30ChgPct")),
        iv30=parse_mixed_numeric(raw_data.get("IV30")),
        hv20=parse_mixed_numeric(raw_data.get("HV20")),
        hv1y=parse_mixed_numeric(raw_data.get("HV1Y")),
        ivr=parse_mixed_numeric(raw_data.get("IVR")),
        iv_52w_p=parse_mixed_numeric(raw_data.get("IV_52W_P")),
        volume=_coerce_int(raw_data.get("Volume")),
        oi_pct_rank=parse_mixed_numeric(raw_data.get("OI_PctRank")),
        earnings=_clean_text(raw_data.get("Earnings")),
        trade_count=_coerce_int(raw_data.get("Trade_Count")),
        batch_id=batch_id,
    )


def _resolve_event_status(raw_earnings: Any, trade_date: date) -> str:
    earnings_date = _parse_earnings_date(raw_earnings)
    if earnings_date is None:
        return "none"
    if earnings_date == trade_date:
        return "today"
    if earnings_date > trade_date:
        return "future"
    return "previous"


def _parse_earnings_date(raw_earnings: Any) -> date | None:
    if not isinstance(raw_earnings, str):
        return None

    normalized_text = raw_earnings.strip()
    if not normalized_text:
        return None

    date_token = normalized_text.split()[0]
    parts = date_token.split("-")
    if len(parts) != 3:
        return None

    day_text, month_text, year_text = parts
    month_value = MONTH_LOOKUP.get(month_text.upper())
    if month_value is None:
        return None

    try:
        return date(int(year_text), month_value, int(day_text))
    except ValueError:
        return None


def _to_probability_tier(value: str) -> ProbabilityTier:
    if value == "mid":
        return ProbabilityTier.MEDIUM
    return ProbabilityTier(value)


def _coerce_int(raw_value: Any) -> int | None:
    numeric_value = parse_mixed_numeric(raw_value)
    if numeric_value is None:
        return None
    if float(numeric_value).is_integer():
        return int(numeric_value)
    return None


def _clean_text(raw_value: Any) -> str | None:
    if not isinstance(raw_value, str):
        return None
    normalized_text = raw_value.strip()
    return normalized_text or None


def _resolve_target_path(target_db: str | Path | None) -> Path:
    if target_db is None:
        return (settings.data_dir / DEFAULT_DATABASE_FILENAME).expanduser().resolve()
    return Path(target_db).expanduser().resolve()


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
