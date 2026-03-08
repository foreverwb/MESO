from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum as SQLEnum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import EarningsRegime, ProbabilityTier, Quadrant, SignalLabel
from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class IngestBatch(Base):
    __tablename__ = "ingest_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    import_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    import_finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    raw_snapshots: Mapped[list["RawOptionSnapshot"]] = relationship(back_populates="batch")
    feature_snapshots: Mapped[list["FeatureSnapshot"]] = relationship(back_populates="batch")
    signal_snapshots: Mapped[list["SignalSnapshot"]] = relationship(back_populates="batch")


class RawOptionSnapshot(Base):
    """One raw symbol-day row per ingest batch to preserve re-import history."""

    __tablename__ = "raw_option_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "trade_date",
            "symbol",
            "batch_id",
        ),
        Index("ix_raw_option_snapshots_trade_date_symbol", "trade_date", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rel_vol_to_90d: Mapped[float | None] = mapped_column("RelVolTo90D", Float, nullable=True)
    call_volume: Mapped[int | None] = mapped_column("CallVolume", Integer, nullable=True)
    put_volume: Mapped[int | None] = mapped_column("PutVolume", Integer, nullable=True)
    put_pct: Mapped[float | None] = mapped_column("PutPct", Float, nullable=True)
    single_leg_pct: Mapped[float | None] = mapped_column("SingleLegPct", Float, nullable=True)
    multi_leg_pct: Mapped[float | None] = mapped_column("MultiLegPct", Float, nullable=True)
    contingent_pct: Mapped[float | None] = mapped_column("ContingentPct", Float, nullable=True)
    rel_notional_to_90d: Mapped[float | None] = mapped_column("RelNotionalTo90D", Float, nullable=True)
    call_notional: Mapped[float | None] = mapped_column("CallNotional", Float, nullable=True)
    put_notional: Mapped[float | None] = mapped_column("PutNotional", Float, nullable=True)
    iv30_chg_pct: Mapped[float | None] = mapped_column("IV30ChgPct", Float, nullable=True)
    iv30: Mapped[float | None] = mapped_column("IV30", Float, nullable=True)
    hv20: Mapped[float | None] = mapped_column("HV20", Float, nullable=True)
    hv1y: Mapped[float | None] = mapped_column("HV1Y", Float, nullable=True)
    ivr: Mapped[float | None] = mapped_column("IVR", Float, nullable=True)
    iv_52w_p: Mapped[float | None] = mapped_column("IV_52W_P", Float, nullable=True)
    volume: Mapped[int | None] = mapped_column("Volume", Integer, nullable=True)
    oi_pct_rank: Mapped[float | None] = mapped_column("OI_PctRank", Float, nullable=True)
    earnings: Mapped[str | None] = mapped_column("Earnings", Text, nullable=True)
    trade_count: Mapped[int | None] = mapped_column("Trade_Count", Integer, nullable=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("ingest_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    batch: Mapped[IngestBatch] = relationship(back_populates="raw_snapshots")


class FeatureSnapshot(Base):
    """One feature symbol-day row per ingest batch to keep derived states versioned."""

    __tablename__ = "feature_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "trade_date",
            "symbol",
            "batch_id",
        ),
        Index("ix_feature_snapshots_trade_date_symbol", "trade_date", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    vol_imb: Mapped[float | None] = mapped_column(Float, nullable=True)
    not_imb: Mapped[float | None] = mapped_column(Float, nullable=True)
    type_imb: Mapped[float | None] = mapped_column(Float, nullable=True)
    vol_gap_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    iv_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    money_rich: Mapped[float | None] = mapped_column(Float, nullable=True)
    imb_agree: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("ingest_batches.id", ondelete="CASCADE"),
        nullable=False,
    )

    batch: Mapped[IngestBatch] = relationship(back_populates="feature_snapshots")


class SignalSnapshot(Base):
    """One signal symbol-day row per ingest batch to support reruns without overwrite."""

    __tablename__ = "signal_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "trade_date",
            "symbol",
            "batch_id",
        ),
        Index("ix_signal_snapshots_trade_date_symbol", "trade_date", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    s_dir: Mapped[float | None] = mapped_column(Float, nullable=True)
    s_vol: Mapped[float | None] = mapped_column(Float, nullable=True)
    s_conf: Mapped[float | None] = mapped_column(Float, nullable=True)
    s_pers: Mapped[float | None] = mapped_column(Float, nullable=True)
    quadrant: Mapped[Quadrant] = mapped_column(
        SQLEnum(Quadrant, native_enum=False, validate_strings=True),
        nullable=False,
    )
    signal_label: Mapped[SignalLabel] = mapped_column(
        SQLEnum(SignalLabel, native_enum=False, validate_strings=True),
        nullable=False,
    )
    event_regime: Mapped[EarningsRegime] = mapped_column(
        SQLEnum(EarningsRegime, native_enum=False, validate_strings=True),
        nullable=False,
    )
    shift_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prob_tier: Mapped[ProbabilityTier] = mapped_column(
        SQLEnum(ProbabilityTier, native_enum=False, validate_strings=True),
        nullable=False,
    )
    is_watchlist: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("ingest_batches.id", ondelete="CASCADE"),
        nullable=False,
    )

    batch: Mapped[IngestBatch] = relationship(back_populates="signal_snapshots")
