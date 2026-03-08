from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    ValidationError,
    model_validator,
)

from app.core.enums import EarningsRegime, ProbabilityTier, Quadrant, SignalLabel
from app.core.exceptions import ConfigError
from app.core.settings import AppSettings, settings

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


REQUIRED_FIELD_MAPPINGS: dict[str, str] = {
    "Relative Volume to 90-Day Avg": "RelVolTo90D",
    "Call Volume": "CallVolume",
    "Put Volume": "PutVolume",
    "Put %": "PutPct",
    "% Single-Leg": "SingleLegPct",
    "% Multi Leg": "MultiLegPct",
    "% ContingentPct": "ContingentPct",
    "Relative Notional to 90-Day Avg": "RelNotionalTo90D",
    "Call $Notional": "CallNotional",
    "Put $Notional": "PutNotional",
    "symbol": "symbol",
    "Volatility % Chg": "IV30ChgPct",
    "Current IV30": "IV30",
    "20-Day Historical Vol": "HV20",
    "1-Year Historical Vol": "HV1Y",
    "IV30 % Rank": "IVR",
    "IV30 52-Week Position": "IV_52W_P",
    "Current Option Volume": "Volume",
    "Open Interest % Rank": "OI_PctRank",
    "Earnings": "Earnings",
    "Trade Count": "Trade_Count",
}


def _default_probability_tiers() -> list[ProbabilityTier]:
    return [
        ProbabilityTier.LOW,
        ProbabilityTier.MEDIUM,
        ProbabilityTier.HIGH,
    ]


def _default_highlight_quadrants() -> list[Quadrant]:
    return [
        Quadrant.BULLISH_EXPANSION,
        Quadrant.BEARISH_EXPANSION,
    ]


def _default_quadrant_labels() -> dict[str, str]:
    return {
        Quadrant.BULLISH_EXPANSION.value: "Bullish Expansion",
        Quadrant.BULLISH_COMPRESSION.value: "Bullish Compression",
        Quadrant.BEARISH_EXPANSION.value: "Bearish Expansion",
        Quadrant.BEARISH_COMPRESSION.value: "Bearish Compression",
    }


class ConfigFileNotFoundError(ConfigError):
    """Raised when a required config file is missing."""


class ConfigValidationError(ConfigError):
    """Raised when a config file fails validation."""


class StrictConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WeightConfig(StrictConfigModel):
    direction_bias: StrictFloat = Field(gt=0.0, lt=1.0)
    volatility_bias: StrictFloat = Field(gt=0.0, lt=1.0)
    structure_confidence: StrictFloat = Field(gt=0.0, lt=1.0)
    persistence: StrictFloat = Field(gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def validate_total_weight(self) -> "WeightConfig":
        total_weight = (
            self.direction_bias
            + self.volatility_bias
            + self.structure_confidence
            + self.persistence
        )
        if not math.isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("weights must sum to 1.0")
        return self


class DirectionCoreWeightConfig(StrictConfigModel):
    not_imb: StrictFloat = Field(gt=0.0, lt=1.0)
    vol_imb: StrictFloat = Field(gt=0.0, lt=1.0)
    type_imb: StrictFloat = Field(gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def validate_total_weight(self) -> "DirectionCoreWeightConfig":
        total_weight = self.not_imb + self.vol_imb + self.type_imb
        if not math.isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("direction.core_weights must sum to 1.0")
        if self.not_imb <= self.vol_imb:
            raise ValueError("direction.core_weights.not_imb must be greater than direction.core_weights.vol_imb")
        return self


class DirectionConvictionWeightConfig(StrictConfigModel):
    single_leg_pct: StrictFloat = Field(gt=0.0, lt=1.0)
    rel_notional_to_90d: StrictFloat = Field(gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def validate_total_weight(self) -> "DirectionConvictionWeightConfig":
        total_weight = self.single_leg_pct + self.rel_notional_to_90d
        if not math.isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("direction.conviction_weights must sum to 1.0")
        return self


class ScoreBoundsConfig(StrictConfigModel):
    clip_min: StrictFloat
    clip_max: StrictFloat

    @model_validator(mode="after")
    def validate_bounds(self) -> "ScoreBoundsConfig":
        if self.clip_min >= self.clip_max:
            raise ValueError("clip_min must be less than clip_max")
        return self


class DirectionScoreConfig(ScoreBoundsConfig):
    core_weights: DirectionCoreWeightConfig
    conviction_weights: DirectionConvictionWeightConfig
    conviction_floor: StrictFloat = Field(ge=0.0, le=1.0)


class VolatilityWeightConfig(StrictConfigModel):
    iv30_chg_pct: StrictFloat = Field(gt=0.0, lt=1.0)
    vol_gap_s: StrictFloat = Field(gt=0.0, lt=1.0)
    iv_level: StrictFloat = Field(gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def validate_total_weight(self) -> "VolatilityWeightConfig":
        total_weight = self.iv30_chg_pct + self.vol_gap_s + self.iv_level
        if not math.isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("volatility.weights must sum to 1.0")
        if not self.iv30_chg_pct > self.vol_gap_s > self.iv_level:
            raise ValueError("volatility.weights must satisfy iv30_chg_pct > vol_gap_s > iv_level")
        return self


class VolatilityScoreConfig(ScoreBoundsConfig):
    weights: VolatilityWeightConfig


class ConfidenceWeightConfig(StrictConfigModel):
    single_leg_pct: StrictFloat = Field(gt=0.0, lt=1.0)
    contingent_pct_inverse: StrictFloat = Field(gt=0.0, lt=1.0)
    trade_count: StrictFloat = Field(gt=0.0, lt=1.0)
    imb_agree: StrictFloat = Field(gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def validate_total_weight(self) -> "ConfidenceWeightConfig":
        total_weight = (
            self.single_leg_pct
            + self.contingent_pct_inverse
            + self.trade_count
            + self.imb_agree
        )
        if not math.isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("confidence.weights must sum to 1.0")
        return self


class ConfidenceScoreConfig(ScoreBoundsConfig):
    weights: ConfidenceWeightConfig


class PersistenceWeightConfig(StrictConfigModel):
    oi_pct_rank: StrictFloat = Field(gt=0.0, lt=1.0)
    rel_notional_to_90d: StrictFloat = Field(gt=0.0, lt=1.0)
    money_rich: StrictFloat = Field(gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def validate_total_weight(self) -> "PersistenceWeightConfig":
        total_weight = self.oi_pct_rank + self.rel_notional_to_90d + self.money_rich
        if not math.isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("persistence.weights must sum to 1.0")
        if self.money_rich >= self.oi_pct_rank or self.money_rich >= self.rel_notional_to_90d:
            raise ValueError("persistence.weights.money_rich must be lower than oi_pct_rank and rel_notional_to_90d")
        return self


class PersistenceScoreConfig(ScoreBoundsConfig):
    weights: PersistenceWeightConfig


class ScoreComponentCommonConfig(StrictConfigModel):
    eps: StrictFloat = Field(gt=0.0, lt=1.0)


class ScoreComponentConfig(StrictConfigModel):
    common: ScoreComponentCommonConfig
    direction: DirectionScoreConfig
    volatility: VolatilityScoreConfig
    confidence: ConfidenceScoreConfig
    persistence: PersistenceScoreConfig


class WinsorizeConfig(StrictConfigModel):
    enabled: StrictBool = True
    lower_quantile: StrictFloat = Field(ge=0.0, lt=1.0)
    upper_quantile: StrictFloat = Field(gt=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_quantile_bounds(self) -> "WinsorizeConfig":
        if self.lower_quantile >= self.upper_quantile:
            raise ValueError(
                "winsorize.lower_quantile must be less than winsorize.upper_quantile",
            )
        return self


class QuantileConfig(StrictConfigModel):
    low: StrictFloat = Field(gt=0.0, lt=1.0)
    medium: StrictFloat = Field(gt=0.0, lt=1.0)
    high: StrictFloat = Field(gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def validate_quantile_order(self) -> "QuantileConfig":
        if not self.low < self.medium < self.high:
            raise ValueError("quantiles must satisfy low < medium < high")
        return self


class QuadrantThresholdConfig(StrictConfigModel):
    direction_cutoff: StrictFloat = Field(ge=0.0, le=1.0)
    volatility_cutoff: StrictFloat = Field(ge=0.0, le=1.0)


class NeutralGateConfig(StrictConfigModel):
    min_confidence: StrictFloat = Field(ge=0.0, le=100.0)
    min_persistence: StrictFloat = Field(ge=0.0, le=100.0)


class LabelThresholdConfig(StrictConfigModel):
    directional_min_abs_direction: StrictFloat = Field(ge=0.0, le=100.0)
    volatility_min_abs_volatility: StrictFloat = Field(ge=0.0, le=100.0)
    today_min_confidence: StrictFloat = Field(ge=0.0, le=100.0)
    today_min_persistence: StrictFloat = Field(ge=0.0, le=100.0)
    today_min_abs_direction: StrictFloat = Field(ge=0.0, le=100.0)
    previous_compression_min_abs_volatility: StrictFloat = Field(ge=0.0, le=100.0)


class ProbabilityTierWeightConfig(StrictConfigModel):
    direction_abs: StrictFloat = Field(gt=0.0, lt=1.0)
    volatility_abs: StrictFloat = Field(gt=0.0, lt=1.0)
    confidence: StrictFloat = Field(gt=0.0, lt=1.0)
    persistence: StrictFloat = Field(gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def validate_total_weight(self) -> "ProbabilityTierWeightConfig":
        total_weight = (
            self.direction_abs
            + self.volatility_abs
            + self.confidence
            + self.persistence
        )
        if not math.isclose(total_weight, 1.0, rel_tol=0.0, abs_tol=1e-9):
            raise ValueError("classification.probability_tiers.weights must sum to 1.0")
        return self


class ProbabilityTierConfig(StrictConfigModel):
    weights: ProbabilityTierWeightConfig
    high_min: StrictFloat = Field(ge=0.0, le=100.0)
    mid_min: StrictFloat = Field(ge=0.0, le=100.0)
    q4_penalty: StrictFloat = Field(ge=0.0, le=100.0)

    @model_validator(mode="after")
    def validate_thresholds(self) -> "ProbabilityTierConfig":
        if self.high_min <= self.mid_min:
            raise ValueError("classification.probability_tiers.high_min must be greater than mid_min")
        return self


class WatchlistConfig(StrictConfigModel):
    min_abs_direction: StrictFloat = Field(ge=0.0, le=100.0)
    min_abs_volatility: StrictFloat = Field(ge=0.0, le=100.0)
    min_confidence: StrictFloat = Field(ge=0.0, le=100.0)
    min_persistence: StrictFloat = Field(ge=0.0, le=100.0)


class EventAdjustmentConfig(StrictConfigModel):
    direction_multiplier: StrictFloat = Field(gt=0.0, le=2.0)
    volatility_multiplier: StrictFloat = Field(gt=0.0, le=2.0)
    confidence_multiplier: StrictFloat = Field(gt=0.0, le=2.0)
    persistence_multiplier: StrictFloat = Field(gt=0.0, le=2.0)


class EventAdjustmentSetConfig(StrictConfigModel):
    today: EventAdjustmentConfig
    future: EventAdjustmentConfig
    previous: EventAdjustmentConfig
    none: EventAdjustmentConfig


class ClassificationConfig(StrictConfigModel):
    neutral_gate: NeutralGateConfig
    label_thresholds: LabelThresholdConfig
    probability_tiers: ProbabilityTierConfig
    watchlist: WatchlistConfig
    event_adjustments: EventAdjustmentSetConfig


class EventFilterConfig(StrictConfigModel):
    relative_volume_multiplier: StrictFloat = Field(gt=0.0)
    relative_notional_multiplier: StrictFloat = Field(gt=0.0)
    trade_count_multiplier: StrictFloat = Field(gt=0.0)
    min_option_volume: StrictInt = Field(default=0, ge=0)


class ShiftDetectionConfig(StrictConfigModel):
    direction_delta: StrictFloat = Field(gt=0.0, le=100.0)
    volatility_delta: StrictFloat = Field(gt=0.0, le=100.0)
    persistence_floor: StrictFloat = Field(ge=0.0, le=100.0)
    median_lookback_days: StrictInt = Field(ge=2, le=90)
    confirmation_days: StrictInt = Field(ge=2, le=5)
    signal_label_on_shift: SignalLabel = SignalLabel.TREND_CHANGE
    probability_floor: ProbabilityTier = ProbabilityTier.MEDIUM


class ScoringConfig(StrictConfigModel):
    weights: WeightConfig
    score_components: ScoreComponentConfig
    winsorize: WinsorizeConfig
    quantiles: QuantileConfig
    quadrant_thresholds: QuadrantThresholdConfig
    classification: ClassificationConfig
    event_filters: EventFilterConfig
    shift_detection: ShiftDetectionConfig


class DefaultFilterConfig(StrictConfigModel):
    earnings_regimes: list[EarningsRegime]
    quadrants: list[Quadrant]
    probability_tiers: list[ProbabilityTier] = Field(default_factory=_default_probability_tiers)
    min_trade_count: StrictInt = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_default_filters(self) -> "DefaultFilterConfig":
        if not self.earnings_regimes:
            raise ValueError("default_filters.earnings_regimes must not be empty")
        if not self.quadrants:
            raise ValueError("default_filters.quadrants must not be empty")
        if not self.probability_tiers:
            raise ValueError("default_filters.probability_tiers must not be empty")
        return self


class HighlightRuleConfig(StrictConfigModel):
    default_signal_label: SignalLabel = SignalLabel.NEUTRAL
    emphasis_probability_tier: ProbabilityTier = ProbabilityTier.HIGH
    highlight_quadrants: list[Quadrant] = Field(default_factory=_default_highlight_quadrants)

    @model_validator(mode="after")
    def validate_highlights(self) -> "HighlightRuleConfig":
        if not self.highlight_quadrants:
            raise ValueError("highlight_rules.highlight_quadrants must not be empty")
        return self


class UIConfig(StrictConfigModel):
    default_date_group_size_days: StrictInt = Field(ge=1)
    default_filters: DefaultFilterConfig
    highlight_rules: HighlightRuleConfig
    quadrant_labels: dict[str, str] = Field(default_factory=_default_quadrant_labels)

    @model_validator(mode="after")
    def validate_quadrant_labels(self) -> "UIConfig":
        expected_keys = set(_default_quadrant_labels())
        actual_keys = set(self.quadrant_labels)
        if expected_keys != actual_keys:
            missing = sorted(expected_keys - actual_keys)
            unexpected = sorted(actual_keys - expected_keys)
            details: list[str] = []
            if missing:
                details.append(f"missing quadrant labels for {missing}")
            if unexpected:
                details.append(f"unexpected quadrant labels for {unexpected}")
            raise ValueError("; ".join(details))
        return self


@dataclass(frozen=True)
class LoadedConfig:
    field_mapping: dict[str, str]
    scoring: ScoringConfig
    ui: UIConfig


class ConfigLoader:
    def __init__(
        self,
        app_settings: AppSettings | None = None,
        config_dir: Path | None = None,
    ) -> None:
        self._settings = app_settings or settings
        self._config_dir = Path(config_dir or self._settings.config_dir)
        self._field_mapping_cache: dict[str, str] | None = None
        self._scoring_cache: ScoringConfig | None = None
        self._ui_cache: UIConfig | None = None

    @property
    def config_dir(self) -> Path:
        return self._config_dir

    def load_all(self) -> LoadedConfig:
        return LoadedConfig(
            field_mapping=self.get_field_mapping(),
            scoring=self.get_scoring(),
            ui=self.get_ui(),
        )

    def get_field_mapping(self) -> dict[str, str]:
        if self._field_mapping_cache is None:
            raw_mapping = self._read_yaml_file("field_mapping.yaml")
            self._field_mapping_cache = self._validate_field_mapping(raw_mapping)
        return self._field_mapping_cache

    def get_scoring(self) -> ScoringConfig:
        if self._scoring_cache is None:
            raw_scoring = self._read_yaml_file("scoring.yaml")
            self._scoring_cache = self._validate_model("scoring.yaml", raw_scoring, ScoringConfig)
        return self._scoring_cache

    def get_ui(self) -> UIConfig:
        if self._ui_cache is None:
            raw_ui = self._read_yaml_file("ui.yaml")
            self._ui_cache = self._validate_model("ui.yaml", raw_ui, UIConfig)
        return self._ui_cache

    def resolve_field_name(self, source_field: str) -> str:
        try:
            return self.get_field_mapping()[source_field]
        except KeyError as exc:
            raise ConfigValidationError(f"Unknown source field: {source_field}") from exc

    def _read_yaml_file(self, file_name: str) -> dict[str, Any]:
        file_path = self.config_dir / file_name
        if not file_path.exists():
            raise ConfigFileNotFoundError(f"Config file not found: {file_path}")

        raw_text = file_path.read_text(encoding="utf-8").strip()
        if not raw_text:
            raise ConfigValidationError(f"{file_name} is empty")

        try:
            if raw_text.startswith("{") or raw_text.startswith("["):
                data = json.loads(raw_text)
            elif yaml is not None:
                data = yaml.safe_load(raw_text)
            else:
                data = json.loads(raw_text)
        except Exception as exc:
            raise ConfigValidationError(f"Failed to parse {file_name}: {exc}") from exc

        if not isinstance(data, dict):
            raise ConfigValidationError(f"{file_name} must contain a top-level mapping")
        return data

    def _validate_field_mapping(self, raw_mapping: dict[str, Any]) -> dict[str, str]:
        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in raw_mapping.items()
        ):
            raise ConfigValidationError(
                "Invalid field_mapping.yaml: all keys and values must be strings",
            )

        expected_keys = set(REQUIRED_FIELD_MAPPINGS)
        actual_keys = set(raw_mapping)
        missing = sorted(expected_keys - actual_keys)
        unexpected = sorted(actual_keys - expected_keys)
        incorrect = sorted(
            key
            for key, expected_value in REQUIRED_FIELD_MAPPINGS.items()
            if key in actual_keys and raw_mapping[key] != expected_value
        )

        details: list[str] = []
        if missing:
            details.append(f"missing required field mappings: {missing}")
        if unexpected:
            details.append(f"unexpected field mappings: {unexpected}")
        if incorrect:
            details.append(
                "incorrect field mapping values: "
                + ", ".join(
                    f"{key} -> {raw_mapping.get(key)!r} (expected {REQUIRED_FIELD_MAPPINGS[key]!r})"
                    for key in incorrect
                ),
            )

        if details:
            raise ConfigValidationError(f"Invalid field_mapping.yaml: {'; '.join(details)}")

        return {key: REQUIRED_FIELD_MAPPINGS[key] for key in REQUIRED_FIELD_MAPPINGS}

    def _validate_model(
        self,
        file_name: str,
        raw_data: dict[str, Any],
        model_cls: type[ScoringConfig] | type[UIConfig],
    ) -> ScoringConfig | UIConfig:
        try:
            return model_cls.model_validate(raw_data)
        except ValidationError as exc:
            errors = []
            for error in exc.errors():
                location = ".".join(str(part) for part in error["loc"]) or "__root__"
                errors.append(f"{location}: {error['msg']}")
            raise ConfigValidationError(f"Invalid {file_name}: {'; '.join(errors)}") from exc
