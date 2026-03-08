from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ImportRowError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    row_number: int = Field(ge=0)
    message: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class NormalizedImportRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    row_number: int = Field(ge=1)
    trade_date: date
    symbol: str = Field(min_length=1, alias="symbol")
    raw_payload_json: dict[str, Any]
    rel_vol_to_90d: float | None = Field(default=None, alias="RelVolTo90D")
    call_volume: int | None = Field(default=None, alias="CallVolume")
    put_volume: int | None = Field(default=None, alias="PutVolume")
    put_pct: float | None = Field(default=None, alias="PutPct")
    single_leg_pct: float | None = Field(default=None, alias="SingleLegPct")
    multi_leg_pct: float | None = Field(default=None, alias="MultiLegPct")
    contingent_pct: float | None = Field(default=None, alias="ContingentPct")
    rel_notional_to_90d: float | None = Field(default=None, alias="RelNotionalTo90D")
    call_notional: float | None = Field(default=None, alias="CallNotional")
    put_notional: float | None = Field(default=None, alias="PutNotional")
    iv30_chg_pct: float | None = Field(default=None, alias="IV30ChgPct")
    iv30: float | None = Field(default=None, alias="IV30")
    hv20: float | None = Field(default=None, alias="HV20")
    hv1y: float | None = Field(default=None, alias="HV1Y")
    ivr: float | None = Field(default=None, alias="IVR")
    iv_52w_p: float | None = Field(default=None, alias="IV_52W_P")
    volume: int | None = Field(default=None, alias="Volume")
    oi_pct_rank: float | None = Field(default=None, alias="OI_PctRank")
    earnings: str | None = Field(default=None, alias="Earnings")
    trade_count: int | None = Field(default=None, alias="Trade_Count")


class ImportSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    batch_id: int = Field(ge=1)
    source_name: str
    source_type: Literal["csv", "json"]
    total_rows: int = Field(ge=0)
    success_rows: int = Field(ge=0)
    signal_rows: int = Field(default=0, ge=0)
    failed_rows: int = Field(ge=0)
    errors: list[ImportRowError] = Field(default_factory=list)
