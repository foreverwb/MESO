from __future__ import annotations

import json
import math
import os
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

ANALYSIS_RECORDS_QUERY = """
SELECT
  symbol,
  trade_date,
  json_extract(payload, '$.raw_data') AS raw_data
FROM analysis_records
ORDER BY trade_date DESC;
"""

REQUIRED_RAW_DATA_FIELDS: tuple[str, ...] = (
    "symbol",
    "RelVolTo90D",
    "CallVolume",
    "PutVolume",
    "PutPct",
    "SingleLegPct",
    "RelNotionalTo90D",
    "CallNotional",
    "PutNotional",
    "IV30ChgPct",
    "IV30",
    "HV20",
    "HV1Y",
    "IVR",
    "IV_52W_P",
    "Volume",
    "OI_PctRank",
    "Earnings",
    "Trade_Count",
)

UNKNOWN_TEXT_VALUES: frozenset[str] = frozenset({"unknown", "unk", "n/a", "na", "none", "null"})


@dataclass(frozen=True, slots=True)
class AnalysisRecord:
    symbol: str
    trade_date: str
    raw_data: str | None


@dataclass(frozen=True, slots=True)
class GroupedAnalysisSamples:
    by_symbol: dict[str, list[AnalysisRecord]]
    by_trade_date: dict[str, list[AnalysisRecord]]
    by_symbol_trade_date: dict[tuple[str, str], list[AnalysisRecord]]


@dataclass(frozen=True, slots=True)
class RawDataParseIssue:
    symbol: str
    trade_date: str
    reason: str


@dataclass(frozen=True, slots=True)
class ParsedRawDataRecord:
    symbol: str
    trade_date: str
    raw_data: dict[str, Any]


@dataclass(frozen=True, slots=True)
class RawDataParseReport:
    parsed_records: list[ParsedRawDataRecord]
    issues: list[RawDataParseIssue]


@dataclass(frozen=True, slots=True)
class FieldPresenceSummary:
    total_records: int
    present_count: int
    missing_count: int
    missing_samples: list[tuple[str, str]]


@dataclass(frozen=True, slots=True)
class OptionalFieldSummary:
    field_name: str
    total_records: int
    present_value_count: int
    missing_key_count: int
    null_value_count: int
    empty_string_count: int
    unknown_value_count: int


@dataclass(frozen=True, slots=True)
class VolumeMismatchRecord:
    symbol: str
    trade_date: str
    call_volume: float
    put_volume: float
    volume: float
    delta: float


@dataclass(frozen=True, slots=True)
class VolumeConsistencySummary:
    checked_count: int
    mismatch_count: int
    mismatches: list[VolumeMismatchRecord]


@dataclass(frozen=True, slots=True)
class PutPctOutlierRecord:
    symbol: str
    trade_date: str
    put_pct_reported: float
    put_pct_recalculated: float
    deviation: float


@dataclass(frozen=True, slots=True)
class PutPctDeviationSummary:
    checked_count: int
    outlier_count: int
    tolerance: float
    max_deviation: float | None
    outliers: list[PutPctOutlierRecord]


def resolve_analysis_records_db_path() -> Path:
    configured_path = os.getenv("ANALYSIS_RECORDS_DB_PATH")
    if configured_path:
        return Path(configured_path).expanduser().resolve()

    return (Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "data" / "analysis_records.db").resolve()


def fetch_analysis_records(db_path: str | Path | None = None) -> list[AnalysisRecord]:
    database_path = Path(db_path).expanduser().resolve() if db_path else resolve_analysis_records_db_path()
    if not database_path.exists():
        raise FileNotFoundError(
            f"analysis_records.db not found at: {database_path}. "
            "Set ANALYSIS_RECORDS_DB_PATH to override the default fixture location.",
        )

    with sqlite3.connect(database_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(ANALYSIS_RECORDS_QUERY).fetchall()

    return [
        AnalysisRecord(
            symbol=row["symbol"],
            trade_date=row["trade_date"],
            raw_data=row["raw_data"],
        )
        for row in rows
    ]


def group_analysis_records(records: Sequence[AnalysisRecord]) -> GroupedAnalysisSamples:
    by_symbol: dict[str, list[AnalysisRecord]] = defaultdict(list)
    by_trade_date: dict[str, list[AnalysisRecord]] = defaultdict(list)
    by_symbol_trade_date: dict[tuple[str, str], list[AnalysisRecord]] = defaultdict(list)

    for record in records:
        by_symbol[record.symbol].append(record)
        by_trade_date[record.trade_date].append(record)
        by_symbol_trade_date[(record.symbol, record.trade_date)].append(record)

    return GroupedAnalysisSamples(
        by_symbol=dict(by_symbol),
        by_trade_date=dict(by_trade_date),
        by_symbol_trade_date=dict(by_symbol_trade_date),
    )


def extract_analysis_samples(
    grouped_samples: GroupedAnalysisSamples,
    *,
    symbol: str | None = None,
    trade_date: str | None = None,
    limit: int | None = None,
) -> list[AnalysisRecord]:
    if symbol and trade_date:
        samples = grouped_samples.by_symbol_trade_date.get((symbol, trade_date), [])
    elif symbol:
        samples = grouped_samples.by_symbol.get(symbol, [])
    elif trade_date:
        samples = grouped_samples.by_trade_date.get(trade_date, [])
    else:
        samples = [record for records in grouped_samples.by_trade_date.values() for record in records]

    return samples[:limit] if limit is not None else list(samples)


def parse_raw_data_records(records: Sequence[AnalysisRecord]) -> RawDataParseReport:
    parsed_records: list[ParsedRawDataRecord] = []
    issues: list[RawDataParseIssue] = []

    for record in records:
        if record.raw_data is None:
            issues.append(
                RawDataParseIssue(
                    symbol=record.symbol,
                    trade_date=record.trade_date,
                    reason="raw_data is null",
                ),
            )
            continue

        try:
            payload = json.loads(record.raw_data)
        except json.JSONDecodeError as exc:
            issues.append(
                RawDataParseIssue(
                    symbol=record.symbol,
                    trade_date=record.trade_date,
                    reason=f"invalid json: {exc.msg}",
                ),
            )
            continue

        if not isinstance(payload, dict):
            issues.append(
                RawDataParseIssue(
                    symbol=record.symbol,
                    trade_date=record.trade_date,
                    reason=f"raw_data is not an object: {type(payload).__name__}",
                ),
            )
            continue

        parsed_records.append(
            ParsedRawDataRecord(
                symbol=record.symbol,
                trade_date=record.trade_date,
                raw_data=payload,
            ),
        )

    return RawDataParseReport(parsed_records=parsed_records, issues=issues)


def summarize_field_presence(
    parsed_records: Sequence[ParsedRawDataRecord],
    field_names: Sequence[str],
    *,
    sample_limit: int = 10,
) -> dict[str, FieldPresenceSummary]:
    summaries: dict[str, FieldPresenceSummary] = {}
    total_records = len(parsed_records)

    for field_name in field_names:
        present_count = 0
        missing_samples: list[tuple[str, str]] = []

        for record in parsed_records:
            if field_name in record.raw_data:
                present_count += 1
                continue

            if len(missing_samples) < sample_limit:
                missing_samples.append((record.symbol, record.trade_date))

        summaries[field_name] = FieldPresenceSummary(
            total_records=total_records,
            present_count=present_count,
            missing_count=total_records - present_count,
            missing_samples=missing_samples,
        )

    return summaries


def normalize_optional_text(value: Any, *, unknown_tokens: frozenset[str] = UNKNOWN_TEXT_VALUES) -> str | None:
    if value is None:
        return None

    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.lower() in unknown_tokens:
            return "Unknown"
        return normalized

    return str(value)


def normalize_earnings(value: Any) -> str | None:
    return normalize_optional_text(value)


def summarize_optional_field(
    parsed_records: Sequence[ParsedRawDataRecord],
    field_name: str,
    *,
    unknown_tokens: frozenset[str] = UNKNOWN_TEXT_VALUES,
) -> OptionalFieldSummary:
    present_value_count = 0
    missing_key_count = 0
    null_value_count = 0
    empty_string_count = 0
    unknown_value_count = 0

    for record in parsed_records:
        if field_name not in record.raw_data:
            missing_key_count += 1
            continue

        value = record.raw_data[field_name]
        if value is None:
            null_value_count += 1
            continue

        if isinstance(value, str):
            normalized = value.strip()
            if not normalized:
                empty_string_count += 1
            elif normalized.lower() in unknown_tokens:
                unknown_value_count += 1
            else:
                present_value_count += 1
            continue

        present_value_count += 1

    return OptionalFieldSummary(
        field_name=field_name,
        total_records=len(parsed_records),
        present_value_count=present_value_count,
        missing_key_count=missing_key_count,
        null_value_count=null_value_count,
        empty_string_count=empty_string_count,
        unknown_value_count=unknown_value_count,
    )


def resolve_tolerance(env_var_name: str, default: float) -> float:
    raw_value = os.getenv(env_var_name)
    if raw_value is None or not raw_value.strip():
        return default

    try:
        tolerance = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{env_var_name} must be a float, got: {raw_value!r}") from exc

    if tolerance < 0:
        raise ValueError(f"{env_var_name} must be non-negative, got: {tolerance}")

    return tolerance


def to_float(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        numeric = float(value)
        if math.isnan(numeric) or math.isinf(numeric):
            return None
        return numeric

    if not isinstance(value, str):
        return None

    normalized = value.strip()
    if not normalized:
        return None

    negative_parentheses = normalized.startswith("(") and normalized.endswith(")")
    if negative_parentheses:
        normalized = normalized[1:-1].strip()

    normalized = normalized.replace(",", "").replace("$", "")
    if normalized.endswith("%"):
        normalized = normalized[:-1].strip()
    if normalized.startswith("+"):
        normalized = normalized[1:].strip()

    try:
        numeric = float(normalized)
    except ValueError:
        return None

    if math.isnan(numeric) or math.isinf(numeric):
        return None

    return -numeric if negative_parentheses else numeric


def build_volume_consistency_summary(
    parsed_records: Sequence[ParsedRawDataRecord],
    *,
    tolerance: float = 0.0,
) -> VolumeConsistencySummary:
    if tolerance < 0:
        raise ValueError(f"tolerance must be non-negative, got: {tolerance}")

    checked_count = 0
    mismatches: list[VolumeMismatchRecord] = []

    for record in parsed_records:
        call_volume = to_float(record.raw_data.get("CallVolume"))
        put_volume = to_float(record.raw_data.get("PutVolume"))
        volume = to_float(record.raw_data.get("Volume"))

        if call_volume is None or put_volume is None or volume is None:
            continue

        checked_count += 1
        delta = volume - (call_volume + put_volume)
        if abs(delta) > tolerance:
            mismatches.append(
                VolumeMismatchRecord(
                    symbol=record.symbol,
                    trade_date=record.trade_date,
                    call_volume=call_volume,
                    put_volume=put_volume,
                    volume=volume,
                    delta=delta,
                ),
            )

    return VolumeConsistencySummary(
        checked_count=checked_count,
        mismatch_count=len(mismatches),
        mismatches=mismatches,
    )


def build_put_pct_deviation_summary(
    parsed_records: Sequence[ParsedRawDataRecord],
    *,
    tolerance: float = 0.2,
) -> PutPctDeviationSummary:
    if tolerance < 0:
        raise ValueError(f"tolerance must be non-negative, got: {tolerance}")

    checked_count = 0
    outliers: list[PutPctOutlierRecord] = []
    max_deviation: float | None = None

    for record in parsed_records:
        call_volume = to_float(record.raw_data.get("CallVolume"))
        put_volume = to_float(record.raw_data.get("PutVolume"))
        put_pct = to_float(record.raw_data.get("PutPct"))

        if call_volume is None or put_volume is None or put_pct is None:
            continue

        total_volume = call_volume + put_volume
        if total_volume == 0:
            continue

        checked_count += 1
        put_pct_recalculated = (put_volume / total_volume) * 100
        deviation = abs(put_pct - put_pct_recalculated)
        max_deviation = deviation if max_deviation is None else max(max_deviation, deviation)

        if deviation > tolerance:
            outliers.append(
                PutPctOutlierRecord(
                    symbol=record.symbol,
                    trade_date=record.trade_date,
                    put_pct_reported=put_pct,
                    put_pct_recalculated=put_pct_recalculated,
                    deviation=deviation,
                ),
            )

    return PutPctDeviationSummary(
        checked_count=checked_count,
        outlier_count=len(outliers),
        tolerance=tolerance,
        max_deviation=max_deviation,
        outliers=outliers,
    )
