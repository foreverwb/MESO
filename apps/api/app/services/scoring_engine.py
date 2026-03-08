from __future__ import annotations

from collections.abc import Callable
import math
from typing import Any

from pydantic import ValidationError

from app.core.exceptions import ScoringError
from app.schemas.scoring_schema import ScoringInputRecord, ScoringRecord
from app.services.config_loader import ConfigLoader


class ScoringEngine:
    def __init__(self, config_loader: ConfigLoader | None = None) -> None:
        self._config_loader = config_loader or ConfigLoader()
        self._scoring_config = self._config_loader.get_scoring()
        self._component_config = self._scoring_config.score_components
        self._eps = self._component_config.common.eps

    def score_direction(self, record: ScoringInputRecord | dict[str, Any]) -> float:
        scoring_record = self._coerce_record(record)
        direction_config = self._component_config.direction

        core_signal = self._weighted_average(
            [
                (scoring_record.not_imb, direction_config.core_weights.not_imb),
                (scoring_record.vol_imb, direction_config.core_weights.vol_imb),
                (scoring_record.type_imb, direction_config.core_weights.type_imb),
            ],
            missing_message="score_direction requires at least one imbalance feature",
        )
        conviction_signal = self._weighted_average(
            [
                (
                    self._positive_component(
                        scoring_record,
                        "single_leg_pct",
                        lambda value: self._clip(value / 100.0, 0.0, 1.0),
                    ),
                    direction_config.conviction_weights.single_leg_pct,
                ),
                (
                    self._positive_component(
                        scoring_record,
                        "rel_notional_to_90d",
                        self._positive_ratio_to_unit,
                    ),
                    direction_config.conviction_weights.rel_notional_to_90d,
                ),
            ],
        ) or 0.0

        # Higher single-leg and relative notional values do not change the sign
        # of direction, they only strengthen how much of the imbalance signal is
        # allowed to pass through.
        multiplier = direction_config.conviction_floor + (
            (1.0 - direction_config.conviction_floor) * conviction_signal
        )
        return self._clip(
            core_signal * 100.0 * multiplier,
            direction_config.clip_min,
            direction_config.clip_max,
        )

    def score_volatility(self, record: ScoringInputRecord | dict[str, Any]) -> float:
        scoring_record = self._coerce_record(record)
        volatility_config = self._component_config.volatility

        signal = self._weighted_average(
            [
                (
                    self._centered_component(
                        scoring_record,
                        "iv30_chg_pct",
                        lambda value: self._clip(value / 100.0, -1.0, 1.0),
                    ),
                    volatility_config.weights.iv30_chg_pct,
                ),
                (
                    self._centered_component(
                        scoring_record,
                        "vol_gap_s",
                        math.tanh,
                    ),
                    volatility_config.weights.vol_gap_s,
                ),
                (
                    self._centered_component(
                        scoring_record,
                        "iv_level",
                        lambda value: self._clip((2.0 * value) - 1.0, -1.0, 1.0),
                    ),
                    volatility_config.weights.iv_level,
                ),
            ],
            missing_message="score_volatility requires at least one volatility input",
        )
        return self._clip(
            signal * 100.0,
            volatility_config.clip_min,
            volatility_config.clip_max,
        )

    def score_confidence(self, record: ScoringInputRecord | dict[str, Any]) -> float:
        scoring_record = self._coerce_record(record)
        confidence_config = self._component_config.confidence

        score = self._weighted_average(
            [
                (
                    self._positive_component(
                        scoring_record,
                        "single_leg_pct",
                        lambda value: self._clip(value / 100.0, 0.0, 1.0),
                    ),
                    confidence_config.weights.single_leg_pct,
                ),
                (
                    self._inverse_positive_component(
                        scoring_record,
                        "contingent_pct",
                        lambda value: self._clip(value / 100.0, 0.0, 1.0),
                    ),
                    confidence_config.weights.contingent_pct_inverse,
                ),
                (
                    self._positive_component(scoring_record, "trade_count"),
                    confidence_config.weights.trade_count,
                ),
                (
                    self._positive_component(
                        scoring_record,
                        "imb_agree",
                        lambda value: self._clip(value, 0.0, 1.0),
                    ),
                    confidence_config.weights.imb_agree,
                ),
            ],
            missing_message="score_confidence requires at least one confidence input",
        )
        return self._clip(
            score * 100.0,
            confidence_config.clip_min,
            confidence_config.clip_max,
        )

    def score_persistence(self, record: ScoringInputRecord | dict[str, Any]) -> float:
        scoring_record = self._coerce_record(record)
        persistence_config = self._component_config.persistence

        score = self._weighted_average(
            [
                (
                    self._positive_component(
                        scoring_record,
                        "oi_pct_rank",
                        lambda value: self._clip(value / 100.0, 0.0, 1.0),
                    ),
                    persistence_config.weights.oi_pct_rank,
                ),
                (
                    self._positive_component(
                        scoring_record,
                        "rel_notional_to_90d",
                        self._positive_ratio_to_unit,
                    ),
                    persistence_config.weights.rel_notional_to_90d,
                ),
                (
                    self._positive_component(
                        scoring_record,
                        "money_rich",
                        self._logistic,
                    ),
                    persistence_config.weights.money_rich,
                ),
            ],
            missing_message="score_persistence requires at least one persistence input",
        )
        return self._clip(
            score * 100.0,
            persistence_config.clip_min,
            persistence_config.clip_max,
        )

    def score_all(self, record: ScoringInputRecord | dict[str, Any]) -> ScoringRecord:
        scoring_record = self._coerce_record(record)
        return ScoringRecord(
            trade_date=scoring_record.trade_date,
            symbol=scoring_record.symbol,
            batch_id=scoring_record.batch_id,
            s_dir=self.score_direction(scoring_record),
            s_vol=self.score_volatility(scoring_record),
            s_conf=self.score_confidence(scoring_record),
            s_pers=self.score_persistence(scoring_record),
        )

    def _coerce_record(self, record: ScoringInputRecord | dict[str, Any]) -> ScoringInputRecord:
        if isinstance(record, ScoringInputRecord):
            return record

        try:
            return ScoringInputRecord.model_validate(record)
        except ValidationError as exc:
            raise ScoringError(
                "Invalid scoring input",
                details={"errors": exc.errors()},
            ) from exc

    def _positive_component(
        self,
        record: ScoringInputRecord,
        field_name: str,
        raw_transform: Callable[[float], float] | None = None,
    ) -> float | None:
        ranked_value = self._ranked_value(record, field_name)
        if ranked_value is not None:
            return self._clip(ranked_value / 100.0, 0.0, 1.0)

        raw_value = getattr(record, field_name)
        if raw_value is None:
            return None
        if raw_transform is None:
            return None
        return self._clip(raw_transform(raw_value), 0.0, 1.0)

    def _inverse_positive_component(
        self,
        record: ScoringInputRecord,
        field_name: str,
        raw_transform: Callable[[float], float],
    ) -> float | None:
        positive_component = self._positive_component(record, field_name, raw_transform)
        if positive_component is None:
            return None
        return 1.0 - positive_component

    def _centered_component(
        self,
        record: ScoringInputRecord,
        field_name: str,
        raw_transform: Callable[[float], float],
    ) -> float | None:
        ranked_value = self._ranked_value(record, field_name)
        if ranked_value is not None:
            return self._clip((ranked_value - 50.0) / 50.0, -1.0, 1.0)

        raw_value = getattr(record, field_name)
        if raw_value is None:
            return None
        return self._clip(raw_transform(raw_value), -1.0, 1.0)

    def _ranked_value(self, record: ScoringInputRecord, field_name: str) -> float | None:
        if record.cross_section_scores is None:
            return None
        return getattr(record.cross_section_scores, field_name)

    def _weighted_average(
        self,
        components: list[tuple[float | None, float]],
        *,
        missing_message: str | None = None,
    ) -> float | None:
        weighted_sum = 0.0
        total_weight = 0.0

        for value, weight in components:
            if value is None:
                continue
            weighted_sum += value * weight
            total_weight += weight

        if total_weight <= self._eps:
            if missing_message is not None:
                raise ScoringError(missing_message)
            return None

        return weighted_sum / total_weight

    def _positive_ratio_to_unit(self, value: float) -> float:
        non_negative_value = max(value, 0.0)
        return non_negative_value / (non_negative_value + 1.0 + self._eps)

    def _logistic(self, value: float) -> float:
        if value >= 0:
            scaled = math.exp(-value)
            return 1.0 / (1.0 + scaled)

        scaled = math.exp(value)
        return scaled / (1.0 + scaled)

    def _clip(self, value: float, lower_bound: float, upper_bound: float) -> float:
        return min(max(value, lower_bound), upper_bound)
