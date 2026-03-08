from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Literal

from sqlalchemy import delete as sqla_delete
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.db.models import FeatureSnapshot, IngestBatch, RawOptionSnapshot, SignalSnapshot
from app.schemas.history_schema import (
    DateGroupSummary,
    DateSignalsResponse,
    DeletedTradeDateSummary,
    HistorySignalRecord,
    SymbolHistoryResponse,
    TrendCategorySummary,
    TrendConsistencyItem,
    TrendConsistencyResponse,
)
from app.services.shift_engine import ShiftEngine


class HistoryService:
    def __init__(
        self,
        session: Session,
        shift_engine: ShiftEngine | None = None,
    ) -> None:
        self._session = session
        self._shift_engine = shift_engine or ShiftEngine()

    def get_signals_for_date(self, trade_date: date | str) -> DateSignalsResponse:
        normalized_trade_date = self._coerce_trade_date(trade_date)
        stmt = (
            select(SignalSnapshot)
            .where(SignalSnapshot.trade_date == normalized_trade_date)
            .order_by(SignalSnapshot.symbol.asc(), desc(SignalSnapshot.batch_id), desc(SignalSnapshot.id))
        )
        snapshots = list(self._session.scalars(stmt))
        latest_snapshots = self._latest_by_key(snapshots, key_func=lambda snapshot: snapshot.symbol)
        items = [self._to_history_record(snapshot) for snapshot in latest_snapshots]
        items.sort(key=lambda item: item.symbol)
        return DateSignalsResponse(
            trade_date=normalized_trade_date,
            total_signals=len(items),
            items=items,
        )

    def get_date_groups(self, limit: int) -> list[DateGroupSummary]:
        stmt = (
            select(SignalSnapshot)
            .order_by(
                SignalSnapshot.trade_date.desc(),
                SignalSnapshot.symbol.asc(),
                desc(SignalSnapshot.batch_id),
                desc(SignalSnapshot.id),
            )
        )
        snapshots = list(self._session.scalars(stmt))
        latest_snapshots = self._latest_by_key(
            snapshots,
            key_func=lambda snapshot: (snapshot.trade_date, snapshot.symbol),
        )

        grouped_records: dict[date, list[HistorySignalRecord]] = defaultdict(list)
        for snapshot in latest_snapshots:
            grouped_records[snapshot.trade_date].append(self._to_history_record(snapshot))

        summaries: list[DateGroupSummary] = []
        for trade_date_value in sorted(grouped_records, reverse=True)[:limit]:
            records = grouped_records[trade_date_value]
            summaries.append(
                DateGroupSummary(
                    trade_date=trade_date_value,
                    total_signals=len(records),
                    directional_count=sum(record.signal_label == "directional_bias" for record in records),
                    directional_symbols=sorted(
                        record.symbol
                        for record in records
                        if record.signal_label == "directional_bias"
                    ),
                    volatility_count=sum(record.signal_label == "volatility_bias" for record in records),
                    volatility_symbols=sorted(
                        record.symbol
                        for record in records
                        if record.signal_label == "volatility_bias"
                    ),
                    neutral_count=sum(record.signal_label == "neutral" for record in records),
                    watchlist_count=sum(record.is_watchlist for record in records),
                ),
            )

        return summaries

    def get_trend_consistency(
        self,
        trade_date: date | str,
        limit: int = 6,
    ) -> TrendConsistencyResponse:
        normalized_trade_date = self._coerce_trade_date(trade_date)
        current_signals = self.get_signals_for_date(normalized_trade_date)
        if current_signals.total_signals == 0:
            return TrendConsistencyResponse(
                trade_date=normalized_trade_date,
                directional=TrendCategorySummary(),
                volatility=TrendCategorySummary(),
            )

        symbols = [item.symbol for item in current_signals.items]
        stmt = (
            select(SignalSnapshot)
            .where(
                SignalSnapshot.trade_date <= normalized_trade_date,
                SignalSnapshot.symbol.in_(symbols),
            )
            .order_by(
                SignalSnapshot.symbol.asc(),
                SignalSnapshot.trade_date.desc(),
                desc(SignalSnapshot.batch_id),
                desc(SignalSnapshot.id),
            )
        )
        snapshots = list(self._session.scalars(stmt))
        latest_snapshots = self._latest_by_key(
            snapshots,
            key_func=lambda snapshot: (snapshot.symbol, snapshot.trade_date),
        )

        histories_by_symbol: dict[str, list[HistorySignalRecord]] = defaultdict(list)
        for snapshot in latest_snapshots:
            histories_by_symbol[snapshot.symbol].append(self._to_history_record(snapshot))

        return TrendConsistencyResponse(
            trade_date=normalized_trade_date,
            directional=self._build_trend_consistency_summary(
                histories_by_symbol=histories_by_symbol,
                score_attr="s_dir",
                limit=limit,
            ),
            volatility=self._build_trend_consistency_summary(
                histories_by_symbol=histories_by_symbol,
                score_attr="s_vol",
                limit=limit,
            ),
        )

    def delete_trade_date(self, trade_date: date | str) -> DeletedTradeDateSummary:
        normalized_trade_date = self._coerce_trade_date(trade_date)
        deleted_raw_rows = self._count_by_trade_date(RawOptionSnapshot, normalized_trade_date)
        deleted_feature_rows = self._count_by_trade_date(FeatureSnapshot, normalized_trade_date)
        deleted_signal_rows = self._count_by_trade_date(SignalSnapshot, normalized_trade_date)

        if deleted_raw_rows + deleted_feature_rows + deleted_signal_rows == 0:
            raise LookupError(f"No snapshot data found for trade_date={normalized_trade_date.isoformat()}")

        affected_batch_ids = self._batch_ids_by_trade_date(normalized_trade_date)
        self._session.execute(
            sqla_delete(SignalSnapshot).where(SignalSnapshot.trade_date == normalized_trade_date),
        )
        self._session.execute(
            sqla_delete(FeatureSnapshot).where(FeatureSnapshot.trade_date == normalized_trade_date),
        )
        self._session.execute(
            sqla_delete(RawOptionSnapshot).where(RawOptionSnapshot.trade_date == normalized_trade_date),
        )

        orphan_batch_ids = [
            batch_id
            for batch_id in affected_batch_ids
            if not self._batch_has_snapshots(batch_id)
        ]
        if orphan_batch_ids:
            self._session.execute(
                sqla_delete(IngestBatch).where(IngestBatch.id.in_(orphan_batch_ids)),
            )

        self._session.commit()
        return DeletedTradeDateSummary(
            trade_date=normalized_trade_date,
            deleted_raw_rows=deleted_raw_rows,
            deleted_feature_rows=deleted_feature_rows,
            deleted_signal_rows=deleted_signal_rows,
            deleted_batch_count=len(orphan_batch_ids),
        )

    def get_symbol_history(self, symbol: str, lookback_days: int) -> SymbolHistoryResponse:
        stmt = (
            select(SignalSnapshot)
            .where(SignalSnapshot.symbol == symbol)
            .order_by(
                SignalSnapshot.trade_date.desc(),
                desc(SignalSnapshot.batch_id),
                desc(SignalSnapshot.id),
            )
        )
        snapshots = list(self._session.scalars(stmt))
        latest_snapshots = self._latest_by_key(
            snapshots,
            key_func=lambda snapshot: snapshot.trade_date,
        )
        latest_snapshots = latest_snapshots[:lookback_days]
        latest_snapshots.sort(key=lambda snapshot: snapshot.trade_date)

        items = [self._to_history_record(snapshot) for snapshot in latest_snapshots]
        shifted_items = self._shift_engine.evaluate(items)
        return SymbolHistoryResponse(
            symbol=symbol,
            lookback_days=lookback_days,
            items=shifted_items,
        )

    def _latest_by_key(self, snapshots: list[SignalSnapshot], key_func) -> list[SignalSnapshot]:
        latest_snapshots = {}
        for snapshot in snapshots:
            key = key_func(snapshot)
            if key not in latest_snapshots:
                latest_snapshots[key] = snapshot
        return list(latest_snapshots.values())

    def _to_history_record(self, snapshot: SignalSnapshot) -> HistorySignalRecord:
        prob_tier = snapshot.prob_tier.value
        if prob_tier == "medium":
            prob_tier = "mid"

        return HistorySignalRecord(
            trade_date=snapshot.trade_date,
            symbol=snapshot.symbol,
            batch_id=snapshot.batch_id,
            s_dir=snapshot.s_dir,
            s_vol=snapshot.s_vol,
            s_conf=snapshot.s_conf,
            s_pers=snapshot.s_pers,
            quadrant=snapshot.quadrant.value,
            signal_label=snapshot.signal_label.value,
            event_regime=snapshot.event_regime.value,
            prob_tier=prob_tier,
            is_watchlist=snapshot.is_watchlist,
        )

    def _build_trend_consistency_summary(
        self,
        *,
        histories_by_symbol: dict[str, list[HistorySignalRecord]],
        score_attr: Literal["s_dir", "s_vol"],
        limit: int,
    ) -> TrendCategorySummary:
        items = []
        for history in histories_by_symbol.values():
            item = self._build_trend_consistency_item(history=history, score_attr=score_attr)
            if item is not None:
                items.append(item)

        overlap_items = [
            item
            for item in items
            if item.trend != "mixed"
        ]
        overlap_items.sort(
            key=lambda item: (
                -(abs(item.delta_3d) + abs(item.delta_5d)),
                item.symbol,
            ),
        )
        delta_3d_items = sorted(
            items,
            key=lambda item: (
                -abs(item.delta_3d),
                item.symbol,
            ),
        )
        delta_5d_items = sorted(
            items,
            key=lambda item: (
                -abs(item.delta_5d),
                item.symbol,
            ),
        )
        return TrendCategorySummary(
            overlap=overlap_items[:limit],
            delta_3d=delta_3d_items[:limit],
            delta_5d=delta_5d_items[:limit],
        )

    def _build_trend_consistency_item(
        self,
        *,
        history: list[HistorySignalRecord],
        score_attr: Literal["s_dir", "s_vol"],
    ) -> TrendConsistencyItem | None:
        if len(history) <= 5:
            return None

        current_score = getattr(history[0], score_attr)
        score_3d = getattr(history[3], score_attr)
        score_5d = getattr(history[5], score_attr)

        if current_score is None or score_3d is None or score_5d is None:
            return None

        delta_3d = current_score - score_3d
        delta_5d = current_score - score_5d
        trend = self._resolve_trend(delta_3d=delta_3d, delta_5d=delta_5d)

        return TrendConsistencyItem(
            symbol=history[0].symbol,
            current_score=current_score,
            delta_3d=delta_3d,
            delta_5d=delta_5d,
            trend=trend,
        )

    def _resolve_trend(
        self,
        *,
        delta_3d: float,
        delta_5d: float,
    ) -> Literal["up", "down", "mixed"]:
        if delta_3d > 0 and delta_5d > 0:
            return "up"
        if delta_3d < 0 and delta_5d < 0:
            return "down"
        return "mixed"

    def _coerce_trade_date(self, value: date | str) -> date:
        if isinstance(value, date):
            return value
        return date.fromisoformat(value)

    def _count_by_trade_date(self, snapshot_model, trade_date_value: date) -> int:
        stmt = (
            select(func.count())
            .select_from(snapshot_model)
            .where(snapshot_model.trade_date == trade_date_value)
        )
        return int(self._session.scalar(stmt) or 0)

    def _batch_ids_by_trade_date(self, trade_date_value: date) -> list[int]:
        batch_ids: set[int] = set()
        for snapshot_model in (RawOptionSnapshot, FeatureSnapshot, SignalSnapshot):
            stmt = (
                select(snapshot_model.batch_id)
                .where(snapshot_model.trade_date == trade_date_value)
                .distinct()
            )
            batch_ids.update(int(batch_id) for batch_id in self._session.scalars(stmt))
        return sorted(batch_ids)

    def _batch_has_snapshots(self, batch_id: int) -> bool:
        for snapshot_model in (RawOptionSnapshot, FeatureSnapshot, SignalSnapshot):
            stmt = select(snapshot_model.id).where(snapshot_model.batch_id == batch_id).limit(1)
            if self._session.scalar(stmt) is not None:
                return True
        return False
