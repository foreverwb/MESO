from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.enums import EarningsRegime, ProbabilityTier, Quadrant, SignalLabel
from app.db.models import SignalSnapshot


@dataclass(frozen=True)
class SignalSnapshotCreate:
    trade_date: date
    symbol: str
    s_dir: float | None
    s_vol: float | None
    s_conf: float | None
    s_pers: float | None
    quadrant: Quadrant
    signal_label: SignalLabel
    event_regime: EarningsRegime
    shift_flag: bool
    prob_tier: ProbabilityTier
    is_watchlist: bool
    batch_id: int


class SignalSnapshotRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def insert_signal_rows(self, rows: list[SignalSnapshotCreate]) -> list[SignalSnapshot]:
        snapshots = [SignalSnapshot(**asdict(row)) for row in rows]
        self._session.add_all(snapshots)
        self._session.flush()
        return snapshots

    def get_signals_by_date(self, trade_date: date) -> list[SignalSnapshot]:
        stmt = (
            select(SignalSnapshot)
            .where(SignalSnapshot.trade_date == trade_date)
            .order_by(SignalSnapshot.symbol.asc(), SignalSnapshot.batch_id.asc())
        )
        return list(self._session.scalars(stmt))

    def get_signal_by_symbol_and_date(
        self,
        symbol: str,
        trade_date: date,
    ) -> SignalSnapshot | None:
        stmt = (
            select(SignalSnapshot)
            .where(
                SignalSnapshot.symbol == symbol,
                SignalSnapshot.trade_date == trade_date,
            )
            .order_by(desc(SignalSnapshot.batch_id), desc(SignalSnapshot.id))
            .limit(1)
        )
        return self._session.scalar(stmt)
