from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import Quadrant, SignalLabel
from app.schemas.scoring_schema import ScoringRecord
from app.services.config_loader import ConfigLoader
from app.services.event_filter import EventAdjustedScoreRecord, EventFilter, EventStatus


QuadrantLabel = Literal[
    "bullish_expansion",
    "bullish_compression",
    "bearish_expansion",
    "bearish_compression",
    "neutral",
]
SignalLabelValue = Literal["neutral", "directional_bias", "volatility_bias"]
ProbabilityTierValue = Literal["high", "mid", "low"]


class ClassifiedSignalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trade_date: date
    symbol: str = Field(min_length=1)
    batch_id: int | None = Field(default=None, ge=1)
    event_status: EventStatus
    event_regime: Literal["pre_earnings", "post_earnings", "neutral"]
    s_dir: float = Field(ge=-100.0, le=100.0)
    s_vol: float = Field(ge=-100.0, le=100.0)
    s_conf: float = Field(ge=0.0, le=100.0)
    s_pers: float = Field(ge=0.0, le=100.0)
    quadrant: QuadrantLabel
    signal_label: SignalLabelValue
    prob_tier: ProbabilityTierValue
    is_watchlist: bool


class SignalClassifier:
    def __init__(
        self,
        config_loader: ConfigLoader | None = None,
        event_filter: EventFilter | None = None,
    ) -> None:
        self._config_loader = config_loader or ConfigLoader()
        self._scoring_config = self._config_loader.get_scoring()
        self._classification_config = self._scoring_config.classification
        self._quadrant_thresholds = self._scoring_config.quadrant_thresholds
        self._event_filter = event_filter or EventFilter(self._config_loader)

    def classify(
        self,
        record: ScoringRecord | dict[str, Any],
        event_status: EventStatus = "none",
    ) -> ClassifiedSignalRecord:
        adjusted = self._event_filter.apply(record, event_status)
        quadrant = self._determine_quadrant(adjusted)
        signal_label = self._determine_signal_label(adjusted, quadrant)

        if self._should_downgrade_to_neutral(adjusted):
            quadrant = "neutral"
            signal_label = SignalLabel.NEUTRAL.value

        if signal_label == SignalLabel.NEUTRAL.value:
            quadrant = "neutral"

        prob_tier = self._determine_prob_tier(adjusted, quadrant)
        is_watchlist = self._determine_watchlist(adjusted, quadrant, signal_label, prob_tier)

        return ClassifiedSignalRecord(
            trade_date=adjusted.trade_date,
            symbol=adjusted.symbol,
            batch_id=adjusted.batch_id,
            event_status=adjusted.event_status,
            event_regime=adjusted.event_regime,
            s_dir=adjusted.s_dir,
            s_vol=adjusted.s_vol,
            s_conf=adjusted.s_conf,
            s_pers=adjusted.s_pers,
            quadrant=quadrant,
            signal_label=signal_label,
            prob_tier=prob_tier,
            is_watchlist=is_watchlist,
        )

    def _determine_quadrant(self, record: EventAdjustedScoreRecord) -> QuadrantLabel:
        direction_cutoff = self._quadrant_thresholds.direction_cutoff * 100.0
        volatility_cutoff = self._quadrant_thresholds.volatility_cutoff * 100.0

        if abs(record.s_dir) <= direction_cutoff or abs(record.s_vol) <= volatility_cutoff:
            return "neutral"
        if record.s_dir > 0 and record.s_vol > 0:
            return Quadrant.BULLISH_EXPANSION.value
        if record.s_dir > 0 and record.s_vol < 0:
            return Quadrant.BULLISH_COMPRESSION.value
        if record.s_dir < 0 and record.s_vol > 0:
            return Quadrant.BEARISH_EXPANSION.value
        return Quadrant.BEARISH_COMPRESSION.value

    def _determine_signal_label(
        self,
        record: EventAdjustedScoreRecord,
        quadrant: QuadrantLabel,
    ) -> SignalLabelValue:
        if quadrant == "neutral":
            return SignalLabel.NEUTRAL.value

        label_thresholds = self._classification_config.label_thresholds

        if (
            record.event_status == "previous"
            and record.s_vol <= -label_thresholds.previous_compression_min_abs_volatility
        ):
            return SignalLabel.VOLATILITY_BIAS.value

        if (
            abs(record.s_dir) >= label_thresholds.directional_min_abs_direction
            and abs(record.s_dir) >= abs(record.s_vol)
        ):
            if record.event_status == "today" and not self._today_direction_allowed(record):
                if abs(record.s_vol) >= label_thresholds.volatility_min_abs_volatility:
                    return SignalLabel.VOLATILITY_BIAS.value
                return SignalLabel.NEUTRAL.value
            return SignalLabel.DIRECTIONAL_BIAS.value

        if abs(record.s_vol) >= label_thresholds.volatility_min_abs_volatility:
            return SignalLabel.VOLATILITY_BIAS.value

        return SignalLabel.NEUTRAL.value

    def _today_direction_allowed(self, record: EventAdjustedScoreRecord) -> bool:
        label_thresholds = self._classification_config.label_thresholds
        return (
            record.s_conf >= label_thresholds.today_min_confidence
            and record.s_pers >= label_thresholds.today_min_persistence
            and abs(record.s_dir) >= label_thresholds.today_min_abs_direction
        )

    def _should_downgrade_to_neutral(self, record: EventAdjustedScoreRecord) -> bool:
        neutral_gate = self._classification_config.neutral_gate
        return (
            record.s_conf < neutral_gate.min_confidence
            or record.s_pers < neutral_gate.min_persistence
        )

    def _determine_prob_tier(
        self,
        record: EventAdjustedScoreRecord,
        quadrant: QuadrantLabel,
    ) -> ProbabilityTierValue:
        if quadrant == "neutral":
            return "low"

        probability_tiers = self._classification_config.probability_tiers
        weights = probability_tiers.weights
        blended_score = (
            abs(record.s_dir) * weights.direction_abs
            + abs(record.s_vol) * weights.volatility_abs
            + record.s_conf * weights.confidence
            + record.s_pers * weights.persistence
        )

        if quadrant == Quadrant.BEARISH_COMPRESSION.value:
            blended_score -= probability_tiers.q4_penalty

        if blended_score >= probability_tiers.high_min:
            return "high"
        if blended_score >= probability_tiers.mid_min:
            return "mid"
        return "low"

    def _determine_watchlist(
        self,
        record: EventAdjustedScoreRecord,
        quadrant: QuadrantLabel,
        signal_label: SignalLabelValue,
        prob_tier: ProbabilityTierValue,
    ) -> bool:
        watchlist = self._classification_config.watchlist
        meets_watchlist_floor = (
            (abs(record.s_dir) >= watchlist.min_abs_direction or abs(record.s_vol) >= watchlist.min_abs_volatility)
            and record.s_conf >= watchlist.min_confidence
            and record.s_pers >= watchlist.min_persistence
        )

        if not meets_watchlist_floor:
            return False
        if quadrant == "neutral" or signal_label == SignalLabel.NEUTRAL.value:
            return True
        return prob_tier == "low"
