from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
import math
from typing import Any

from app.services.config_loader import ConfigLoader


RANKABLE_FIELDS: dict[str, tuple[str, ...]] = {
    "single_leg_pct": ("single_leg_pct", "SingleLegPct"),
    "contingent_pct": ("contingent_pct", "ContingentPct"),
    "rel_notional_to_90d": ("rel_notional_to_90d", "RelNotionalTo90D"),
    "rel_vol_to_90d": ("rel_vol_to_90d", "RelVolTo90D"),
    "trade_count": ("trade_count", "Trade_Count"),
    "iv30_chg_pct": ("iv30_chg_pct", "IV30ChgPct"),
    "vol_gap_s": ("vol_gap_s",),
    "iv_level": ("iv_level",),
    "oi_pct_rank": ("oi_pct_rank", "OI_PctRank"),
    "money_rich": ("money_rich",),
    "imb_agree": ("imb_agree",),
}


class CrossSectionRanker:
    def __init__(self, config_loader: ConfigLoader | None = None) -> None:
        self._config_loader = config_loader or ConfigLoader()
        winsorize = self._config_loader.get_scoring().winsorize
        self._winsorize_enabled = winsorize.enabled
        self._lower_quantile = winsorize.lower_quantile
        self._upper_quantile = winsorize.upper_quantile

    def rank_records(self, records_or_frame: Any) -> list[dict[str, Any]]:
        records = self._coerce_records(records_or_frame)
        canonical_records = [self._canonicalize_record(record) for record in records]

        grouped_indices: dict[date, list[int]] = defaultdict(list)
        for index, record in enumerate(canonical_records):
            grouped_indices[self._coerce_trade_date(record["trade_date"])].append(index)
            record["trade_date"] = self._coerce_trade_date(record["trade_date"])

        ranked_records = [self._initialize_ranked_record(record) for record in canonical_records]

        for trade_date, indices in grouped_indices.items():
            group_records = [canonical_records[index] for index in indices]
            group_scores = self._rank_group(group_records)

            for group_offset, index in enumerate(indices):
                ranked_records[index]["trade_date"] = trade_date
                ranked_records[index]["cross_section_scores"] = group_scores[group_offset]

        return ranked_records

    def _coerce_records(self, records_or_frame: Any) -> list[dict[str, Any]]:
        if isinstance(records_or_frame, list):
            return [dict(record) for record in records_or_frame]

        to_dict = getattr(records_or_frame, "to_dict", None)
        if callable(to_dict):
            records = to_dict("records")
            if isinstance(records, list):
                return [dict(record) for record in records]

        raise TypeError("CrossSectionRanker expects a record list or a DataFrame-like object with to_dict('records').")

    def _canonicalize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        canonical_record = dict(record)

        for canonical_field, aliases in RANKABLE_FIELDS.items():
            for alias in aliases:
                if alias in canonical_record:
                    canonical_record[canonical_field] = canonical_record[alias]
                    break

        return canonical_record

    def _initialize_ranked_record(self, record: dict[str, Any]) -> dict[str, Any]:
        ranked_record = dict(record)
        ranked_record["cross_section_scores"] = {
            field_name: None for field_name in RANKABLE_FIELDS
        }
        return ranked_record

    def _rank_group(self, records: list[dict[str, Any]]) -> list[dict[str, float | None]]:
        group_scores = [
            {field_name: None for field_name in RANKABLE_FIELDS}
            for _ in records
        ]

        for field_name in RANKABLE_FIELDS:
            values = [record.get(field_name) for record in records]
            ranked_values = self._rank_field(values)

            for index, ranked_value in enumerate(ranked_values):
                group_scores[index][field_name] = ranked_value

        return group_scores

    def _rank_field(self, values: list[Any]) -> list[float | None]:
        numeric_indices: list[int] = []
        numeric_values: list[float] = []

        for index, value in enumerate(values):
            coerced_value = self._coerce_numeric(value)
            if coerced_value is None:
                continue
            numeric_indices.append(index)
            numeric_values.append(coerced_value)

        ranked_values: list[float | None] = [None] * len(values)
        if not numeric_values:
            return ranked_values

        winsorized_values = self._winsorize_values(numeric_values)
        percentile_map = self._compute_percentile_map(winsorized_values)

        for source_index, winsorized_value in zip(numeric_indices, winsorized_values, strict=True):
            ranked_values[source_index] = percentile_map[winsorized_value]

        return ranked_values

    def _winsorize_values(self, values: list[float]) -> list[float]:
        if not self._winsorize_enabled or len(values) < 2:
            return list(values)

        sorted_values = sorted(values)
        lower_bound = self._compute_quantile(sorted_values, self._lower_quantile)
        upper_bound = self._compute_quantile(sorted_values, self._upper_quantile)
        return [
            min(max(value, lower_bound), upper_bound)
            for value in values
        ]

    def _compute_percentile_map(self, values: list[float]) -> dict[float, float]:
        sorted_values = sorted(values)
        unique_scores: dict[float, float] = {}
        total_count = len(sorted_values)
        cursor = 0

        # Hazen plotting positions keep tiny samples stable: one observation maps to 50,
        # two observations map to 25/75 instead of 0/100, and all-identical values share
        # the same neutral score. None values are excluded earlier and remain None.
        while cursor < total_count:
            value = sorted_values[cursor]
            start = cursor
            while cursor + 1 < total_count and sorted_values[cursor + 1] == value:
                cursor += 1
            end = cursor
            average_rank = (start + end) / 2 + 1
            unique_scores[value] = ((average_rank - 0.5) / total_count) * 100
            cursor += 1

        return unique_scores

    def _compute_quantile(self, sorted_values: list[float], quantile: float) -> float:
        if len(sorted_values) == 1:
            return sorted_values[0]

        position = (len(sorted_values) - 1) * quantile
        lower_index = math.floor(position)
        upper_index = math.ceil(position)

        if lower_index == upper_index:
            return sorted_values[lower_index]

        lower_value = sorted_values[lower_index]
        upper_value = sorted_values[upper_index]
        weight = position - lower_index
        return lower_value + (upper_value - lower_value) * weight

    def _coerce_trade_date(self, value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
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
        raise ValueError(f"trade_date is not parseable: {value!r}")

    def _coerce_numeric(self, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise TypeError(f"Boolean values are not valid rank inputs: {value!r}")
        if isinstance(value, (int, float)):
            return float(value)
        raise TypeError(f"Non-numeric rank input: {value!r}")
