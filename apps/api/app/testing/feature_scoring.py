from __future__ import annotations

import math
from typing import Any, Iterable

from app.core.exceptions import ScoringError
from app.schemas.feature_schema import FeatureSnapshotRecord
from app.schemas.scoring_schema import ScoringRecord
from app.services.feature_engine import FeatureEngine
from app.services.scoring_engine import ScoringEngine
from app.testing.analysis_records import ParsedRawDataRecord

FEATURE_SCORING_INPUT_FIELDS: tuple[str, ...] = (
    "CallVolume",
    "PutVolume",
    "CallNotional",
    "PutNotional",
    "RelVolTo90D",
    "RelNotionalTo90D",
    "IV30",
    "HV20",
    "IVR",
    "IV_52W_P",
    "SingleLegPct",
    "ContingentPct",
    "Trade_Count",
    "IV30ChgPct",
    "OI_PctRank",
)

CORE_FEATURE_FIELDS: tuple[str, ...] = (
    "vol_imb",
    "not_imb",
    "type_imb",
    "vol_gap_s",
    "iv_level",
    "imb_agree",
    "money_rich",
)

CORE_SCORE_FIELDS: tuple[str, ...] = (
    "s_dir",
    "s_vol",
    "s_conf",
    "s_pers",
)

NUMERIC_SUFFIX_MULTIPLIERS: dict[str, float] = {
    "K": 1_000.0,
    "M": 1_000_000.0,
    "B": 1_000_000_000.0,
}

NULL_LIKE_TEXT: frozenset[str] = frozenset({"", "na", "n/a", "null", "none"})


def parse_mixed_numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        numeric_value = float(value)
        if math.isnan(numeric_value) or math.isinf(numeric_value):
            return None
        return numeric_value

    if not isinstance(value, str):
        return None

    raw_text = value.strip()
    if not raw_text or raw_text.lower() in NULL_LIKE_TEXT:
        return None

    negative_parentheses = raw_text.startswith("(") and raw_text.endswith(")")
    if negative_parentheses:
        raw_text = raw_text[1:-1].strip()

    multiplier = 1.0
    if raw_text:
        suffix = raw_text[-1].upper()
        if suffix in NUMERIC_SUFFIX_MULTIPLIERS:
            multiplier = NUMERIC_SUFFIX_MULTIPLIERS[suffix]
            raw_text = raw_text[:-1].strip()

    normalized_text = raw_text.replace(",", "").replace("$", "").strip()
    if normalized_text.endswith("%"):
        normalized_text = normalized_text[:-1].strip()
    if normalized_text.startswith("+"):
        normalized_text = normalized_text[1:].strip()

    if not normalized_text:
        return None

    try:
        numeric_value = float(normalized_text)
    except ValueError:
        return None

    if math.isnan(numeric_value) or math.isinf(numeric_value):
        return None

    if negative_parentheses:
        numeric_value = -numeric_value

    return numeric_value * multiplier


def build_feature_scoring_source(parsed_record: ParsedRawDataRecord) -> dict[str, Any]:
    source: dict[str, Any] = {
        "trade_date": parsed_record.trade_date,
        "symbol": parsed_record.raw_data.get("symbol", parsed_record.symbol),
    }

    for field_name in FEATURE_SCORING_INPUT_FIELDS:
        source[field_name] = parse_mixed_numeric(parsed_record.raw_data.get(field_name))

    return source


def compute_feature_and_scores(
    parsed_record: ParsedRawDataRecord,
    *,
    feature_engine: FeatureEngine | None = None,
    scoring_engine: ScoringEngine | None = None,
) -> tuple[FeatureSnapshotRecord, ScoringRecord]:
    feature_engine = feature_engine or FeatureEngine()
    scoring_engine = scoring_engine or ScoringEngine()

    source = build_feature_scoring_source(parsed_record)
    feature_record = feature_engine.build_feature_record(source)
    scoring_input = source | feature_record.model_dump(mode="python")
    scoring_record = scoring_engine.score_all(scoring_input)
    return feature_record, scoring_record


def find_parsed_record(
    parsed_records: Iterable[ParsedRawDataRecord],
    *,
    symbol: str,
    trade_date: str,
) -> ParsedRawDataRecord | None:
    for record in parsed_records:
        if record.symbol == symbol and record.trade_date == trade_date:
            return record
    return None


def find_record_with_high_iv_52w_p(
    parsed_records: Iterable[ParsedRawDataRecord],
) -> ParsedRawDataRecord | None:
    for record in parsed_records:
        iv_52w_p = parse_mixed_numeric(record.raw_data.get("IV_52W_P"))
        if iv_52w_p is not None and iv_52w_p > 100:
            return record
    return None


def try_score_record(
    parsed_record: ParsedRawDataRecord,
    *,
    feature_engine: FeatureEngine | None = None,
    scoring_engine: ScoringEngine | None = None,
) -> tuple[FeatureSnapshotRecord, ScoringRecord | None, Exception | None]:
    feature_engine = feature_engine or FeatureEngine()
    scoring_engine = scoring_engine or ScoringEngine()

    source = build_feature_scoring_source(parsed_record)
    feature_record = feature_engine.build_feature_record(source)
    scoring_input = source | feature_record.model_dump(mode="python")
    try:
        scoring_record = scoring_engine.score_all(scoring_input)
    except Exception as exc:  # pragma: no cover - assertion is in tests
        return feature_record, None, exc
    return feature_record, scoring_record, None


def is_scoring_input_error(exc: Exception) -> bool:
    return isinstance(exc, ScoringError) and "Invalid scoring input" in str(exc)
