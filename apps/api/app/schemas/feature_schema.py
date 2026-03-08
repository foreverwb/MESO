from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FeatureSourceRecord(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True, populate_by_name=True)

    trade_date: date
    symbol: str = Field(min_length=1)
    batch_id: int | None = Field(default=None, ge=1)
    call_volume: float | None = Field(default=None, alias="CallVolume")
    put_volume: float | None = Field(default=None, alias="PutVolume")
    call_notional: float | None = Field(default=None, alias="CallNotional")
    put_notional: float | None = Field(default=None, alias="PutNotional")
    rel_vol_to_90d: float | None = Field(default=None, alias="RelVolTo90D")
    rel_notional_to_90d: float | None = Field(default=None, alias="RelNotionalTo90D")
    iv30: float | None = Field(default=None, alias="IV30")
    hv20: float | None = Field(default=None, alias="HV20")
    ivr: float | None = Field(default=None, alias="IVR")
    iv_52w_p: float | None = Field(default=None, alias="IV_52W_P")


class FeatureSnapshotRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trade_date: date
    symbol: str = Field(min_length=1)
    vol_imb: float | None = None
    not_imb: float | None = None
    type_imb: float | None = None
    vol_gap_s: float | None = None
    iv_level: float | None = None
    money_rich: float | None = None
    imb_agree: float | None = None
    batch_id: int | None = Field(default=None, ge=1)


class FeatureBatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    records: list[FeatureSnapshotRecord] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
