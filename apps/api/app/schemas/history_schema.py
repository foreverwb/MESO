from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ShiftState = Literal["none", "pending", "confirmed"]
TrendDirection = Literal["up", "down", "mixed"]


class HistorySignalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trade_date: date
    symbol: str = Field(min_length=1)
    batch_id: int = Field(ge=1)
    s_dir: float | None = Field(default=None, ge=-100.0, le=100.0)
    s_vol: float | None = Field(default=None, ge=-100.0, le=100.0)
    s_conf: float | None = Field(default=None, ge=0.0, le=100.0)
    s_pers: float | None = Field(default=None, ge=0.0, le=100.0)
    quadrant: str
    signal_label: str
    event_regime: str
    prob_tier: str
    is_watchlist: bool
    shift_state: ShiftState = "none"
    median_s_dir: float | None = None
    median_s_vol: float | None = None
    delta_dir: float | None = Field(default=None, ge=0.0)
    delta_vol: float | None = Field(default=None, ge=0.0)


class DateSignalsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trade_date: date
    total_signals: int = Field(ge=0)
    items: list[HistorySignalRecord] = Field(default_factory=list)


class DateGroupSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trade_date: date
    total_signals: int = Field(ge=0)
    directional_count: int = Field(ge=0)
    directional_symbols: list[str] = Field(default_factory=list)
    volatility_count: int = Field(ge=0)
    volatility_symbols: list[str] = Field(default_factory=list)
    neutral_count: int = Field(ge=0)
    watchlist_count: int = Field(ge=0)


class DeletedTradeDateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trade_date: date
    deleted_raw_rows: int = Field(ge=0)
    deleted_feature_rows: int = Field(ge=0)
    deleted_signal_rows: int = Field(ge=0)
    deleted_batch_count: int = Field(ge=0)


class TrendConsistencyItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(min_length=1)
    current_score: float = Field(ge=-100.0, le=100.0)
    delta_3d: float
    delta_5d: float
    trend: TrendDirection


class TrendCategorySummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    overlap: list[TrendConsistencyItem] = Field(default_factory=list)
    delta_3d: list[TrendConsistencyItem] = Field(default_factory=list)
    delta_5d: list[TrendConsistencyItem] = Field(default_factory=list)


class TrendConsistencyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trade_date: date
    directional: TrendCategorySummary = Field(default_factory=TrendCategorySummary)
    volatility: TrendCategorySummary = Field(default_factory=TrendCategorySummary)


class SymbolHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str = Field(min_length=1)
    lookback_days: int = Field(ge=1)
    items: list[HistorySignalRecord] = Field(default_factory=list)
