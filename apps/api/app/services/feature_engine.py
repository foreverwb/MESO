from __future__ import annotations

import math
from typing import Any

from app.schemas.feature_schema import FeatureBatchResult, FeatureSnapshotRecord, FeatureSourceRecord


FEATURE_EPS = 1e-9
TYPE_IMB_WEIGHTS = {"not_imb": 0.6, "vol_imb": 0.4}
IV_LEVEL_WEIGHTS = {"ivr": 0.5, "iv_52w_p": 0.5}


class FeatureEngine:
    def __init__(self, *, eps: float = FEATURE_EPS) -> None:
        self._eps = eps

    def build_feature_record(
        self,
        raw_record: FeatureSourceRecord | dict[str, Any],
    ) -> FeatureSnapshotRecord:
        source_record = self._coerce_source_record(raw_record)

        vol_imb = self._compute_imbalance(
            positive=source_record.call_volume,
            negative=source_record.put_volume,
        )
        not_imb = self._compute_imbalance(
            positive=source_record.call_notional,
            negative=source_record.put_notional,
        )

        return FeatureSnapshotRecord(
            trade_date=source_record.trade_date,
            symbol=source_record.symbol,
            vol_imb=vol_imb,
            not_imb=not_imb,
            type_imb=self._compute_type_imb(vol_imb=vol_imb, not_imb=not_imb),
            vol_gap_s=self._safe_log_ratio(
                numerator=source_record.iv30,
                denominator=source_record.hv20,
            ),
            iv_level=self._compute_iv_level(
                ivr=source_record.ivr,
                iv_52w_p=source_record.iv_52w_p,
            ),
            money_rich=self._safe_log_ratio(
                numerator=source_record.rel_notional_to_90d,
                denominator=source_record.rel_vol_to_90d,
            ),
            imb_agree=self._compute_imb_agree(vol_imb=vol_imb, not_imb=not_imb),
            batch_id=source_record.batch_id,
        )

    def build_feature_records(
        self,
        raw_records: list[FeatureSourceRecord | dict[str, Any]],
    ) -> FeatureBatchResult:
        records: list[FeatureSnapshotRecord] = []
        errors: list[dict[str, Any]] = []

        for row_index, raw_record in enumerate(raw_records, start=1):
            try:
                records.append(self.build_feature_record(raw_record))
            except Exception as exc:
                errors.append(
                    {
                        "row_index": row_index,
                        "reason": str(exc),
                        "raw_record": raw_record if isinstance(raw_record, dict) else raw_record.model_dump(mode="json"),
                    },
                )

        return FeatureBatchResult(records=records, errors=errors)

    def _coerce_source_record(
        self,
        raw_record: FeatureSourceRecord | dict[str, Any],
    ) -> FeatureSourceRecord:
        if isinstance(raw_record, FeatureSourceRecord):
            return raw_record
        return FeatureSourceRecord.model_validate(raw_record)

    def _compute_imbalance(
        self,
        *,
        positive: float | None,
        negative: float | None,
    ) -> float | None:
        if positive is None or negative is None:
            return None
        denominator = positive + negative + self._eps
        return (positive - negative) / denominator

    def _compute_type_imb(
        self,
        *,
        vol_imb: float | None,
        not_imb: float | None,
    ) -> float | None:
        if vol_imb is None or not_imb is None:
            return None
        return (
            TYPE_IMB_WEIGHTS["not_imb"] * not_imb
            + TYPE_IMB_WEIGHTS["vol_imb"] * vol_imb
        )

    def _compute_iv_level(
        self,
        *,
        ivr: float | None,
        iv_52w_p: float | None,
    ) -> float | None:
        if ivr is None or iv_52w_p is None:
            return None
        return (
            IV_LEVEL_WEIGHTS["ivr"] * self._normalize_unit_interval(ivr)
            + IV_LEVEL_WEIGHTS["iv_52w_p"] * self._normalize_unit_interval(iv_52w_p)
        )

    def _compute_imb_agree(
        self,
        *,
        vol_imb: float | None,
        not_imb: float | None,
    ) -> float | None:
        if vol_imb is None or not_imb is None:
            return None
        return max(0.0, 1 - abs(vol_imb - not_imb) / 2)

    def _normalize_unit_interval(self, value: float) -> float:
        if value > 1:
            value = value / 100
        return min(1.0, max(0.0, value))

    def _safe_log_ratio(
        self,
        *,
        numerator: float | None,
        denominator: float | None,
    ) -> float | None:
        # Missing inputs propagate to None so downstream scoring can decide explicitly
        # whether the feature should be skipped or imputed.
        if numerator is None or denominator is None:
            return None

        # HV20 <= 0 makes ln(IV30 / HV20) undefined. The same guard is used for
        # money_rich because ln(RelNotionalTo90D / RelVolTo90D) also requires both
        # sides of the ratio to stay strictly positive.
        if numerator <= 0 or denominator <= 0:
            return None

        return math.log(numerator / denominator)
