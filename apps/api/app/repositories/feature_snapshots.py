from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.db.models import FeatureSnapshot


@dataclass(frozen=True)
class FeatureSnapshotCreate:
    trade_date: date
    symbol: str
    vol_imb: float | None
    not_imb: float | None
    type_imb: float | None
    vol_gap_s: float | None
    iv_level: float | None
    money_rich: float | None
    imb_agree: bool | None
    batch_id: int


class FeatureSnapshotRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def insert_feature_rows(self, rows: list[FeatureSnapshotCreate]) -> list[FeatureSnapshot]:
        snapshots = [FeatureSnapshot(**asdict(row)) for row in rows]
        self._session.add_all(snapshots)
        self._session.flush()
        return snapshots
