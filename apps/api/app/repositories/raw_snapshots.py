from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import RawOptionSnapshot


@dataclass(frozen=True)
class RawSnapshotCreate:
    trade_date: date
    symbol: str
    raw_payload_json: dict[str, Any]
    batch_id: int
    rel_vol_to_90d: float | None = None
    call_volume: int | None = None
    put_volume: int | None = None
    put_pct: float | None = None
    single_leg_pct: float | None = None
    multi_leg_pct: float | None = None
    contingent_pct: float | None = None
    rel_notional_to_90d: float | None = None
    call_notional: float | None = None
    put_notional: float | None = None
    iv30_chg_pct: float | None = None
    iv30: float | None = None
    hv20: float | None = None
    hv1y: float | None = None
    ivr: float | None = None
    iv_52w_p: float | None = None
    volume: int | None = None
    oi_pct_rank: float | None = None
    earnings: str | None = None
    trade_count: int | None = None


class RawSnapshotRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def insert_raw_rows(self, rows: list[RawSnapshotCreate]) -> list[RawOptionSnapshot]:
        snapshots = [RawOptionSnapshot(**asdict(row)) for row in rows]
        self._session.add_all(snapshots)
        self._session.flush()
        return snapshots
