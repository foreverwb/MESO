from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.schemas.import_schema import ImportRowError, NormalizedImportRow
from app.services.config_loader import ConfigLoader


STRUCTURAL_SOURCE_FIELDS = {"trade_date", "Trade Date", "date"}
TEXT_STANDARD_FIELDS = {"symbol", "Earnings"}
INTEGER_STANDARD_FIELDS = {"CallVolume", "PutVolume", "Volume", "Trade_Count"}
NULL_LIKE_VALUES = {"", "na", "n/a", "null", "none"}
NUMERIC_SUFFIX_MULTIPLIERS = {
    "K": 1_000.0,
    "M": 1_000_000.0,
    "B": 1_000_000_000.0,
}


@dataclass(frozen=True)
class NormalizationResult:
    rows: list[NormalizedImportRow]
    errors: list[ImportRowError]


class ImportNormalizer:
    def __init__(self, config_loader: ConfigLoader | None = None) -> None:
        self._config_loader = config_loader or ConfigLoader()
        self._field_mapping = self._config_loader.get_field_mapping()
        self._accepted_fields = set(self._field_mapping) | set(self._field_mapping.values()) | STRUCTURAL_SOURCE_FIELDS

    def normalize_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        trade_date_override: date | None = None,
        ignore_unknown_fields: bool = False,
    ) -> NormalizationResult:
        normalized_rows: list[NormalizedImportRow] = []
        errors: list[ImportRowError] = []

        for row_number, raw_row in enumerate(rows, start=1):
            try:
                normalized_rows.append(
                    self.normalize_row(
                        raw_row,
                        row_number=row_number,
                        trade_date_override=trade_date_override,
                        ignore_unknown_fields=ignore_unknown_fields,
                    ),
                )
            except ValueError as exc:
                errors.append(
                    ImportRowError(
                        row_number=row_number,
                        message=str(exc),
                        raw_payload=self._clean_raw_row(raw_row),
                    ),
                )

        return NormalizationResult(rows=normalized_rows, errors=errors)

    def normalize_row(
        self,
        raw_row: dict[str, Any],
        *,
        row_number: int,
        trade_date_override: date | None = None,
        ignore_unknown_fields: bool = False,
    ) -> NormalizedImportRow:
        cleaned_raw_row = self._clean_raw_row(raw_row)
        raw_payload = dict(cleaned_raw_row)
        if trade_date_override is not None:
            raw_payload["trade_date"] = trade_date_override.isoformat()

        unknown_fields = sorted(field_name for field_name in raw_payload if field_name not in self._accepted_fields)
        if unknown_fields and not ignore_unknown_fields:
            raise ValueError(f"Unknown fields: {unknown_fields}")

        standardized_row: dict[str, Any] = {
            "row_number": row_number,
            "trade_date": trade_date_override or self._parse_trade_date(raw_payload),
            "raw_payload_json": raw_payload,
        }

        for source_field, raw_value in raw_payload.items():
            if source_field in STRUCTURAL_SOURCE_FIELDS:
                continue

            standard_field = self._resolve_standard_field(source_field)
            if standard_field is None:
                continue

            standardized_row[standard_field] = self._normalize_standard_value(
                standard_field,
                raw_value,
            )

        symbol = standardized_row.get("symbol")
        if symbol is None:
            raise ValueError("Missing required field: symbol")
        standardized_row["symbol"] = symbol.strip()
        if not standardized_row["symbol"]:
            raise ValueError("Missing required field: symbol")

        return NormalizedImportRow.model_validate(standardized_row)

    def _clean_raw_row(self, raw_row: dict[str, Any]) -> dict[str, Any]:
        cleaned: dict[str, Any] = {}
        for key, value in raw_row.items():
            if key is None:
                continue
            normalized_key = str(key).strip()
            if not normalized_key:
                continue
            cleaned[normalized_key] = value
        return cleaned

    def _resolve_standard_field(self, source_field: str) -> str | None:
        if source_field in self._field_mapping:
            return self._field_mapping[source_field]
        if source_field in self._field_mapping.values():
            return source_field
        return None

    def _parse_trade_date(self, raw_row: dict[str, Any]) -> date:
        for source_field in STRUCTURAL_SOURCE_FIELDS:
            if source_field in raw_row:
                raw_value = raw_row[source_field]
                break
        else:
            raise ValueError("Missing required field: trade_date")

        if self._is_null_like(raw_value):
            raise ValueError("Missing required field: trade_date")
        if isinstance(raw_value, datetime):
            return raw_value.date()
        if isinstance(raw_value, date):
            return raw_value
        if not isinstance(raw_value, str):
            raise ValueError(f"Invalid trade_date value: {raw_value!r}")

        raw_text = raw_value.strip()
        try:
            return date.fromisoformat(raw_text)
        except ValueError:
            pass

        for fmt in ("%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(raw_text, fmt).date()
            except ValueError:
                continue

        raise ValueError(f"Invalid trade_date value: {raw_value!r}")

    def _normalize_standard_value(self, standard_field: str, raw_value: Any) -> str | int | float | None:
        if self._is_null_like(raw_value):
            return None
        if standard_field in TEXT_STANDARD_FIELDS:
            return str(raw_value).strip()
        if standard_field in INTEGER_STANDARD_FIELDS:
            return self._parse_integer(standard_field, raw_value)
        return self._parse_float(standard_field, raw_value)

    def _parse_integer(self, standard_field: str, raw_value: Any) -> int:
        numeric_value = self._parse_numeric_value(standard_field, raw_value)
        if not numeric_value.is_integer():
            raise ValueError(f"Invalid integer value for {standard_field}: {raw_value!r}")
        return int(numeric_value)

    def _parse_float(self, standard_field: str, raw_value: Any) -> float:
        return self._parse_numeric_value(standard_field, raw_value)

    def _parse_numeric_value(self, standard_field: str, raw_value: Any) -> float:
        if isinstance(raw_value, bool):
            raise ValueError(f"Invalid numeric value for {standard_field}: {raw_value!r}")
        if isinstance(raw_value, (int, float)):
            return float(raw_value)

        raw_text = str(raw_value).strip()
        is_negative = raw_text.startswith("(") and raw_text.endswith(")")
        if is_negative:
            raw_text = raw_text[1:-1].strip()

        multiplier = 1.0
        if raw_text:
            suffix = raw_text[-1].upper()
            if suffix in NUMERIC_SUFFIX_MULTIPLIERS:
                multiplier = NUMERIC_SUFFIX_MULTIPLIERS[suffix]
                raw_text = raw_text[:-1].strip()

        normalized_text = raw_text.replace(",", "").replace("$", "").replace("%", "").strip()
        if normalized_text.startswith("+"):
            normalized_text = normalized_text[1:].strip()
        if is_negative:
            normalized_text = f"-{normalized_text}"
        try:
            return float(normalized_text) * multiplier
        except ValueError as exc:
            raise ValueError(f"Invalid numeric value for {standard_field}: {raw_value!r}") from exc

    def _is_null_like(self, raw_value: Any) -> bool:
        if raw_value is None:
            return True
        if isinstance(raw_value, str) and raw_value.strip().lower() in NULL_LIKE_VALUES:
            return True
        return False
