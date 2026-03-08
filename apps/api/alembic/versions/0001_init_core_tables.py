"""init core tables

Revision ID: 0001_init_core_tables
Revises:
Create Date: 2026-03-08 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_init_core_tables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


quadrant_enum = sa.Enum(
    "bullish_expansion",
    "bullish_compression",
    "bearish_expansion",
    "bearish_compression",
    name="quadrant",
    native_enum=False,
)
signal_label_enum = sa.Enum(
    "neutral",
    "directional_bias",
    "volatility_bias",
    "trend_change",
    name="signallabel",
    native_enum=False,
)
earnings_regime_enum = sa.Enum(
    "pre_earnings",
    "post_earnings",
    "neutral",
    name="earningsregime",
    native_enum=False,
)
probability_tier_enum = sa.Enum(
    "low",
    "medium",
    "high",
    name="probabilitytier",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "ingest_batches",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("import_started_at", sa.DateTime(), nullable=False),
        sa.Column("import_finished_at", sa.DateTime(), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("summary_json", sa.JSON(), nullable=False),
    )

    op.create_table(
        "raw_option_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("raw_payload_json", sa.JSON(), nullable=False),
        sa.Column("RelVolTo90D", sa.Float(), nullable=True),
        sa.Column("CallVolume", sa.Integer(), nullable=True),
        sa.Column("PutVolume", sa.Integer(), nullable=True),
        sa.Column("PutPct", sa.Float(), nullable=True),
        sa.Column("SingleLegPct", sa.Float(), nullable=True),
        sa.Column("MultiLegPct", sa.Float(), nullable=True),
        sa.Column("ContingentPct", sa.Float(), nullable=True),
        sa.Column("RelNotionalTo90D", sa.Float(), nullable=True),
        sa.Column("CallNotional", sa.Float(), nullable=True),
        sa.Column("PutNotional", sa.Float(), nullable=True),
        sa.Column("IV30ChgPct", sa.Float(), nullable=True),
        sa.Column("IV30", sa.Float(), nullable=True),
        sa.Column("HV20", sa.Float(), nullable=True),
        sa.Column("HV1Y", sa.Float(), nullable=True),
        sa.Column("IVR", sa.Float(), nullable=True),
        sa.Column("IV_52W_P", sa.Float(), nullable=True),
        sa.Column("Volume", sa.Integer(), nullable=True),
        sa.Column("OI_PctRank", sa.Float(), nullable=True),
        sa.Column("Earnings", sa.Text(), nullable=True),
        sa.Column("Trade_Count", sa.Integer(), nullable=True),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["ingest_batches.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("trade_date", "symbol", "batch_id"),
    )
    op.create_index(
        "ix_raw_option_snapshots_trade_date_symbol",
        "raw_option_snapshots",
        ["trade_date", "symbol"],
        unique=False,
    )

    op.create_table(
        "feature_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("vol_imb", sa.Float(), nullable=True),
        sa.Column("not_imb", sa.Float(), nullable=True),
        sa.Column("type_imb", sa.Float(), nullable=True),
        sa.Column("vol_gap_s", sa.Float(), nullable=True),
        sa.Column("iv_level", sa.Float(), nullable=True),
        sa.Column("money_rich", sa.Float(), nullable=True),
        sa.Column("imb_agree", sa.Boolean(), nullable=True),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["ingest_batches.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("trade_date", "symbol", "batch_id"),
    )
    op.create_index(
        "ix_feature_snapshots_trade_date_symbol",
        "feature_snapshots",
        ["trade_date", "symbol"],
        unique=False,
    )

    op.create_table(
        "signal_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("s_dir", sa.Float(), nullable=True),
        sa.Column("s_vol", sa.Float(), nullable=True),
        sa.Column("s_conf", sa.Float(), nullable=True),
        sa.Column("s_pers", sa.Float(), nullable=True),
        sa.Column("quadrant", quadrant_enum, nullable=False),
        sa.Column("signal_label", signal_label_enum, nullable=False),
        sa.Column("event_regime", earnings_regime_enum, nullable=False),
        sa.Column("shift_flag", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("prob_tier", probability_tier_enum, nullable=False),
        sa.Column("is_watchlist", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["ingest_batches.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("trade_date", "symbol", "batch_id"),
    )
    op.create_index(
        "ix_signal_snapshots_trade_date_symbol",
        "signal_snapshots",
        ["trade_date", "symbol"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_signal_snapshots_trade_date_symbol", table_name="signal_snapshots")
    op.drop_table("signal_snapshots")
    op.drop_index("ix_feature_snapshots_trade_date_symbol", table_name="feature_snapshots")
    op.drop_table("feature_snapshots")
    op.drop_index("ix_raw_option_snapshots_trade_date_symbol", table_name="raw_option_snapshots")
    op.drop_table("raw_option_snapshots")
    op.drop_table("ingest_batches")
