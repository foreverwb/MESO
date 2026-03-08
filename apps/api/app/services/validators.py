from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import EarningsRegime
from app.core.exceptions import DomainValidationError, ImportValidationError
from app.schemas.import_schema import NormalizedImportRow


SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,15}$")
NON_NEGATIVE_FIELDS = {
    "volume": "Volume",
    "call_volume": "CallVolume",
    "put_volume": "PutVolume",
    "trade_count": "Trade_Count",
    "call_notional": "CallNotional",
    "put_notional": "PutNotional",
}
PERCENTAGE_RANGE_FIELDS = {
    "put_pct": "PutPct",
    "single_leg_pct": "SingleLegPct",
    "multi_leg_pct": "MultiLegPct",
    "contingent_pct": "ContingentPct",
    "ivr": "IVR",
    "oi_pct_rank": "OI_PctRank",
    "iv_52w_p": "IV_52W_P",
}
EARNINGS_ALIASES = {
    "neutral": EarningsRegime.NEUTRAL,
    "none": EarningsRegime.NEUTRAL,
    "no": EarningsRegime.NEUTRAL,
    "post_earnings": EarningsRegime.POST_EARNINGS,
    "post-earnings": EarningsRegime.POST_EARNINGS,
    "post earnings": EarningsRegime.POST_EARNINGS,
    "after earnings": EarningsRegime.POST_EARNINGS,
    "pre_earnings": EarningsRegime.PRE_EARNINGS,
    "pre-earnings": EarningsRegime.PRE_EARNINGS,
    "pre earnings": EarningsRegime.PRE_EARNINGS,
    "before earnings": EarningsRegime.PRE_EARNINGS,
}
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


class ValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    raw_value: Any = None
    reason: str
    row_index: int | None = Field(default=None, ge=1)


class RecordValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    passed_record: dict[str, Any] | None = None
    errors: list[ValidationIssue] = Field(default_factory=list)


class FailedRecordValidation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    row_index: int | None = Field(default=None, ge=1)
    record: dict[str, Any] = Field(default_factory=dict)
    errors: list[ValidationIssue] = Field(default_factory=list)


class BatchValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    passed_records: list[dict[str, Any]] = Field(default_factory=list)
    failed_records: list[FailedRecordValidation] = Field(default_factory=list)


def validate_record(
    record: NormalizedImportRow | dict[str, Any],
    *,
    row_index: int | None = None,
    raise_on_error: bool = False,
) -> RecordValidationResult:
    canonical_record = _canonicalize_record(record)
    effective_row_index = row_index or canonical_record.get("row_number")

    issues: list[ValidationIssue] = []

    symbol = canonical_record.get("symbol")
    if symbol is None or not isinstance(symbol, str) or not symbol.strip():
        issues.append(_issue("symbol", symbol, "symbol must be a non-empty string", effective_row_index))
    elif not SYMBOL_PATTERN.fullmatch(symbol.strip()):
        issues.append(_issue("symbol", symbol, "symbol contains unsupported characters", effective_row_index))
    else:
        canonical_record["symbol"] = symbol.strip()

    trade_date_value = canonical_record.get("trade_date")
    parsed_trade_date = _coerce_date(trade_date_value)
    if parsed_trade_date is None:
        issues.append(_issue("trade_date", trade_date_value, "trade_date must be parseable as a date", effective_row_index))
    else:
        canonical_record["trade_date"] = parsed_trade_date

    for field_name, display_name in NON_NEGATIVE_FIELDS.items():
        raw_value = canonical_record.get(field_name)
        if raw_value is not None and raw_value < 0:
            issues.append(_issue(display_name, raw_value, "value must be non-negative", effective_row_index))

    for field_name, display_name in PERCENTAGE_RANGE_FIELDS.items():
        raw_value = canonical_record.get(field_name)
        if raw_value is not None and not 0 <= raw_value <= 100:
            issues.append(_issue(display_name, raw_value, "value must be between 0 and 100", effective_row_index))

    call_volume = canonical_record.get("call_volume")
    put_volume = canonical_record.get("put_volume")
    if call_volume is not None and put_volume is not None and call_volume == 0 and put_volume == 0:
        issues.append(
            _issue(
                "CallVolume/PutVolume",
                {"CallVolume": call_volume, "PutVolume": put_volume},
                "CallVolume and PutVolume cannot both be 0",
                effective_row_index,
            ),
        )

    call_notional = canonical_record.get("call_notional")
    put_notional = canonical_record.get("put_notional")
    if call_notional is not None and put_notional is not None and call_notional == 0 and put_notional == 0:
        issues.append(
            _issue(
                "CallNotional/PutNotional",
                {"CallNotional": call_notional, "PutNotional": put_notional},
                "CallNotional and PutNotional cannot both be 0 when both fields are present",
                effective_row_index,
            ),
        )

    earnings_value = canonical_record.get("earnings")
    if earnings_value is not None:
        normalized_earnings = _normalize_earnings_value(earnings_value)
        if normalized_earnings is None:
            issues.append(
                _issue(
                    "Earnings",
                    earnings_value,
                    "Earnings must map to a supported earnings regime or earnings date text",
                    effective_row_index,
                ),
            )
        else:
            canonical_record["earnings"] = normalized_earnings

    result = RecordValidationResult(
        passed_record=None if issues else canonical_record,
        errors=issues,
    )

    if issues and raise_on_error:
        raise ImportValidationError(
            "Record validation failed",
            details={"errors": [issue.model_dump(mode="json") for issue in issues]},
        )

    return result


def validate_records(
    records: list[NormalizedImportRow | dict[str, Any]],
    *,
    raise_on_error: bool = False,
) -> BatchValidationResult:
    passed_records: list[dict[str, Any]] = []
    failed_records: list[FailedRecordValidation] = []

    for index, record in enumerate(records, start=1):
        result = validate_record(record, row_index=index, raise_on_error=False)
        if result.errors:
            failed_records.append(
                FailedRecordValidation(
                    row_index=index,
                    record=_canonicalize_record(record),
                    errors=result.errors,
                ),
            )
        else:
            passed_records.append(result.passed_record or {})

    if failed_records and raise_on_error:
        raise ImportValidationError(
            "Batch validation failed",
            details={
                "failed_records": [
                    failed_record.model_dump(mode="json")
                    for failed_record in failed_records
                ],
            },
        )

    return BatchValidationResult(
        passed_records=passed_records,
        failed_records=failed_records,
    )


def resolve_earnings_regime(value: str | None) -> EarningsRegime | None:
    if value is None:
        return None

    resolved_regime = _resolve_earnings_regime(value)
    if resolved_regime is None:
        raise DomainValidationError(
            "Unsupported earnings regime",
            details={"field": "Earnings", "raw_value": value},
        )
    return resolved_regime


def _canonicalize_record(record: NormalizedImportRow | dict[str, Any]) -> dict[str, Any]:
    if isinstance(record, NormalizedImportRow):
        return record.model_dump()

    canonical_record: dict[str, Any] = {}
    field_lookup = _field_lookup()
    for key, value in record.items():
        canonical_key = field_lookup.get(str(key), str(key))
        canonical_record[canonical_key] = value
    return canonical_record


def _field_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for field_name, model_field in NormalizedImportRow.model_fields.items():
        lookup[field_name] = field_name
        if model_field.alias:
            lookup[model_field.alias] = field_name
    return lookup


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None

    raw_text = value.strip()
    try:
        return date.fromisoformat(raw_text)
    except ValueError:
        pass

    for fmt in ("%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(raw_text, fmt).date()
        except ValueError:
            continue
    return None


def _resolve_earnings_regime(value: Any) -> EarningsRegime | None:
    if isinstance(value, EarningsRegime):
        return value
    if not isinstance(value, str):
        return None

    normalized_value = value.strip().lower()
    if not normalized_value:
        return None
    return EARNINGS_ALIASES.get(normalized_value)


def _normalize_earnings_value(value: Any) -> str | None:
    if isinstance(value, EarningsRegime):
        return value.value
    if not isinstance(value, str):
        return None

    normalized_value = value.strip()
    if not normalized_value:
        return None

    resolved_regime = _resolve_earnings_regime(normalized_value)
    if resolved_regime is not None:
        return resolved_regime.value
    if _parse_earnings_date(normalized_value) is not None:
        return normalized_value
    return None


def _parse_earnings_date(value: str) -> date | None:
    date_token = value.split()[0]
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


def _issue(field: str, raw_value: Any, reason: str, row_index: int | None) -> ValidationIssue:
    return ValidationIssue(
        field=field,
        raw_value=raw_value,
        reason=reason,
        row_index=row_index,
    )
