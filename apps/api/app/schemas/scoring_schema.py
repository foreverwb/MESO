from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class CrossSectionScoreRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    single_leg_pct: float | None = Field(default=None, ge=0.0, le=100.0, alias="SingleLegPct")
    contingent_pct: float | None = Field(default=None, ge=0.0, le=100.0, alias="ContingentPct")
    rel_notional_to_90d: float | None = Field(
        default=None,
        ge=0.0,
        le=100.0,
        alias="RelNotionalTo90D",
    )
    rel_vol_to_90d: float | None = Field(default=None, ge=0.0, le=100.0, alias="RelVolTo90D")
    trade_count: float | None = Field(default=None, ge=0.0, le=100.0, alias="Trade_Count")
    iv30_chg_pct: float | None = Field(default=None, ge=0.0, le=100.0, alias="IV30ChgPct")
    vol_gap_s: float | None = Field(default=None, ge=0.0, le=100.0)
    iv_level: float | None = Field(default=None, ge=0.0, le=100.0)
    oi_pct_rank: float | None = Field(default=None, ge=0.0, le=100.0, alias="OI_PctRank")
    money_rich: float | None = Field(default=None, ge=0.0, le=100.0)
    imb_agree: float | None = Field(default=None, ge=0.0, le=100.0)


class ScoringInputRecord(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True, populate_by_name=True)

    trade_date: date
    symbol: str = Field(min_length=1)
    batch_id: int | None = Field(default=None, ge=1)

    single_leg_pct: float | None = Field(default=None, ge=0.0, le=100.0, alias="SingleLegPct")
    contingent_pct: float | None = Field(default=None, ge=0.0, le=100.0, alias="ContingentPct")
    rel_notional_to_90d: float | None = Field(default=None, ge=0.0, alias="RelNotionalTo90D")
    trade_count: float | None = Field(default=None, ge=0.0, alias="Trade_Count")
    iv30_chg_pct: float | None = Field(default=None, alias="IV30ChgPct")
    oi_pct_rank: float | None = Field(default=None, ge=0.0, le=100.0, alias="OI_PctRank")

    vol_imb: float | None = Field(default=None, ge=-1.0, le=1.0)
    not_imb: float | None = Field(default=None, ge=-1.0, le=1.0)
    type_imb: float | None = Field(default=None, ge=-1.0, le=1.0)
    vol_gap_s: float | None = None
    iv_level: float | None = Field(default=None, ge=0.0, le=1.0)
    money_rich: float | None = None
    imb_agree: float | None = Field(default=None, ge=0.0, le=1.0)

    cross_section_scores: CrossSectionScoreRecord | None = None


class ScoringRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trade_date: date
    symbol: str = Field(min_length=1)
    batch_id: int | None = Field(default=None, ge=1)
    s_dir: float = Field(ge=-100.0, le=100.0)
    s_vol: float = Field(ge=-100.0, le=100.0)
    s_conf: float = Field(ge=0.0, le=100.0)
    s_pers: float = Field(ge=0.0, le=100.0)
