from __future__ import annotations

from datetime import date
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


DataT = TypeVar("DataT")


class ApiMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    count: int | None = Field(default=None, ge=0)
    limit: int | None = Field(default=None, ge=1)
    trade_date: date | None = None
    symbol: str | None = None
    lookback_days: int | None = Field(default=None, ge=1)


class ApiError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    details: dict[str, Any] | None = None


class ApiResponse(BaseModel, Generic[DataT]):
    model_config = ConfigDict(extra="forbid", frozen=True)

    data: DataT | None = None
    meta: ApiMeta = Field(default_factory=ApiMeta)
    error: ApiError | None = None


class HealthPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str


class FiltersPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_statuses: list[str]
    quadrants: list[str]
    signal_labels: list[str]
    probability_tiers: list[str]
    default_date_group_size_days: int = Field(ge=1)
    default_filters: dict[str, Any]
    highlight_rules: dict[str, Any]


class ChartPoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    trade_date: date
    x_score: float
    y_score: float
    bubble_size: float = Field(ge=0.0)
    quadrant: str
    signal_label: str
    s_conf: float | None = Field(default=None, ge=0.0, le=100.0)
    s_pers: float | None = Field(default=None, ge=0.0, le=100.0)
    highlight: bool
