from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.core.enums import EarningsRegime
from app.core.exceptions import ScoringError
from app.schemas.scoring_schema import ScoringRecord
from app.services.config_loader import ConfigLoader


EventStatus = Literal["today", "future", "previous", "none"]
EventRegime = Literal["pre_earnings", "post_earnings", "neutral"]


class EventAdjustedScoreRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trade_date: date
    symbol: str = Field(min_length=1)
    batch_id: int | None = Field(default=None, ge=1)
    event_status: EventStatus
    event_regime: EventRegime
    s_dir: float = Field(ge=-100.0, le=100.0)
    s_vol: float = Field(ge=-100.0, le=100.0)
    s_conf: float = Field(ge=0.0, le=100.0)
    s_pers: float = Field(ge=0.0, le=100.0)


class EventFilter:
    def __init__(self, config_loader: ConfigLoader | None = None) -> None:
        self._config_loader = config_loader or ConfigLoader()
        self._scoring_config = self._config_loader.get_scoring()
        self._classification_config = self._scoring_config.classification
        self._score_components = self._scoring_config.score_components

    def apply(
        self,
        record: ScoringRecord | dict[str, Any],
        event_status: EventStatus = "none",
    ) -> EventAdjustedScoreRecord:
        scoring_record = self._coerce_record(record)
        normalized_status = self._normalize_status(event_status)
        adjustment = getattr(self._classification_config.event_adjustments, normalized_status)

        return EventAdjustedScoreRecord(
            trade_date=scoring_record.trade_date,
            symbol=scoring_record.symbol,
            batch_id=scoring_record.batch_id,
            event_status=normalized_status,
            event_regime=self._map_event_regime(normalized_status),
            s_dir=self._clip(
                scoring_record.s_dir * adjustment.direction_multiplier,
                self._score_components.direction.clip_min,
                self._score_components.direction.clip_max,
            ),
            s_vol=self._clip(
                scoring_record.s_vol * adjustment.volatility_multiplier,
                self._score_components.volatility.clip_min,
                self._score_components.volatility.clip_max,
            ),
            s_conf=self._clip(
                scoring_record.s_conf * adjustment.confidence_multiplier,
                self._score_components.confidence.clip_min,
                self._score_components.confidence.clip_max,
            ),
            s_pers=self._clip(
                scoring_record.s_pers * adjustment.persistence_multiplier,
                self._score_components.persistence.clip_min,
                self._score_components.persistence.clip_max,
            ),
        )

    def _coerce_record(self, record: ScoringRecord | dict[str, Any]) -> ScoringRecord:
        if isinstance(record, ScoringRecord):
            return record

        try:
            return ScoringRecord.model_validate(record)
        except ValidationError as exc:
            raise ScoringError(
                "Invalid event filter input",
                details={"errors": exc.errors()},
            ) from exc

    def _normalize_status(self, event_status: str) -> EventStatus:
        normalized_status = event_status.strip().lower()
        if normalized_status not in {"today", "future", "previous", "none"}:
            raise ScoringError(f"Unsupported event status: {event_status}")
        return normalized_status  # type: ignore[return-value]

    def _map_event_regime(self, event_status: EventStatus) -> EventRegime:
        if event_status in {"today", "future"}:
            return EarningsRegime.PRE_EARNINGS.value
        if event_status == "previous":
            return EarningsRegime.POST_EARNINGS.value
        return EarningsRegime.NEUTRAL.value

    def _clip(self, value: float, lower_bound: float, upper_bound: float) -> float:
        return min(max(value, lower_bound), upper_bound)
