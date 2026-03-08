from __future__ import annotations

from statistics import median

from app.schemas.history_schema import HistorySignalRecord
from app.services.config_loader import ConfigLoader


class ShiftEngine:
    def __init__(self, config_loader: ConfigLoader | None = None) -> None:
        self._config_loader = config_loader or ConfigLoader()
        self._shift_config = self._config_loader.get_scoring().shift_detection

    def evaluate(
        self,
        records: list[HistorySignalRecord],
    ) -> list[HistorySignalRecord]:
        if not records:
            return []

        sorted_records = sorted(records, key=lambda record: record.trade_date)
        evaluated_records: list[HistorySignalRecord] = []
        active_quadrant: str | None = None
        streak_length = 0

        for index, record in enumerate(sorted_records):
            prior_records = evaluated_records[-self._shift_config.median_lookback_days :]
            median_s_dir = self._median_value(prior_records, "s_dir")
            median_s_vol = self._median_value(prior_records, "s_vol")
            delta_dir = self._delta(record.s_dir, median_s_dir)
            delta_vol = self._delta(record.s_vol, median_s_vol)
            thresholds_met = (
                delta_dir is not None
                and delta_vol is not None
                and delta_dir >= self._shift_config.direction_delta
                and delta_vol >= self._shift_config.volatility_delta
            )
            persistence_met = (
                record.s_pers is not None
                and record.s_pers >= self._shift_config.persistence_floor
            )

            shift_state = "none"
            previous_record = evaluated_records[-1] if evaluated_records else None
            switched_quadrant = (
                previous_record is not None
                and record.quadrant != "neutral"
                and previous_record.quadrant != "neutral"
                and record.quadrant != previous_record.quadrant
            )
            continues_shift = (
                active_quadrant is not None
                and record.quadrant == active_quadrant
                and thresholds_met
                and persistence_met
            )

            if switched_quadrant and thresholds_met and persistence_met:
                active_quadrant = record.quadrant
                streak_length = 1
                shift_state = "pending"
            elif continues_shift:
                streak_length += 1
                shift_state = (
                    "confirmed"
                    if streak_length >= self._shift_config.confirmation_days
                    else "pending"
                )
            else:
                active_quadrant = None
                streak_length = 0

            evaluated_records.append(
                record.model_copy(
                    update={
                        "shift_state": shift_state,
                        "median_s_dir": median_s_dir,
                        "median_s_vol": median_s_vol,
                        "delta_dir": delta_dir,
                        "delta_vol": delta_vol,
                    },
                ),
            )

        return evaluated_records

    def _median_value(
        self,
        records: list[HistorySignalRecord],
        field_name: str,
    ) -> float | None:
        values = [
            getattr(record, field_name)
            for record in records
            if getattr(record, field_name) is not None
        ]
        if not values:
            return None
        return float(median(values))

    def _delta(self, current_value: float | None, median_value: float | None) -> float | None:
        if current_value is None or median_value is None:
            return None
        return abs(current_value - median_value)
