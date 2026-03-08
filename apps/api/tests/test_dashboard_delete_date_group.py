from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import select

from app.core.enums import EarningsRegime, ProbabilityTier, Quadrant, SignalLabel
from app.db.models import FeatureSnapshot, IngestBatch, RawOptionSnapshot, SignalSnapshot
from app.db.session import (
    build_database_url,
    create_engine_from_url,
    create_session_factory,
    get_db_session,
    init_db,
)
from app.main import app


@pytest.fixture()
def client_with_db(tmp_path: Path):
    database_path = tmp_path / "app.db"
    engine = create_engine_from_url(build_database_url(database_path))
    init_db(engine)
    session_factory = create_session_factory(engine)

    def override_get_db_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_get_db_session
    client = TestClient(app)

    try:
        yield client, session_factory
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_delete_date_group_removes_only_requested_trade_date_and_orphan_batches(
    client_with_db,
) -> None:
    client, session_factory = client_with_db

    with session_factory() as session:
        orphan_batch = _create_batch(session, "orphan.json")
        retained_batch = _create_batch(session, "retained.json")
        untouched_batch = _create_batch(session, "untouched.json")

        _add_snapshot_triplet(session, batch_id=orphan_batch.id, symbol="AAPL", trade_date_value=date(2026, 3, 17))
        _add_snapshot_triplet(session, batch_id=retained_batch.id, symbol="MSFT", trade_date_value=date(2026, 3, 17))
        _add_snapshot_triplet(session, batch_id=retained_batch.id, symbol="MSFT", trade_date_value=date(2026, 3, 18))
        _add_snapshot_triplet(session, batch_id=untouched_batch.id, symbol="NVDA", trade_date_value=date(2026, 3, 16))
        session.commit()

    response = client.delete("/api/v1/date-groups/2026-03-17")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data"] == {
        "trade_date": "2026-03-17",
        "deleted_raw_rows": 2,
        "deleted_feature_rows": 2,
        "deleted_signal_rows": 2,
        "deleted_batch_count": 1,
    }

    with session_factory() as session:
        remaining_batches = list(session.scalars(select(IngestBatch).order_by(IngestBatch.id.asc())))
        remaining_raw = list(session.scalars(select(RawOptionSnapshot).order_by(RawOptionSnapshot.trade_date.asc())))
        remaining_features = list(session.scalars(select(FeatureSnapshot).order_by(FeatureSnapshot.trade_date.asc())))
        remaining_signals = list(session.scalars(select(SignalSnapshot).order_by(SignalSnapshot.trade_date.asc())))

    assert [batch.source_name for batch in remaining_batches] == ["retained.json", "untouched.json"]
    assert [snapshot.trade_date.isoformat() for snapshot in remaining_raw] == ["2026-03-16", "2026-03-18"]
    assert [snapshot.trade_date.isoformat() for snapshot in remaining_features] == ["2026-03-16", "2026-03-18"]
    assert [snapshot.trade_date.isoformat() for snapshot in remaining_signals] == ["2026-03-16", "2026-03-18"]


def test_delete_date_group_returns_not_found_when_trade_date_is_absent(client_with_db) -> None:
    client, _ = client_with_db

    response = client.delete("/api/v1/date-groups/2026-03-17")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["message"] == "No snapshot data found for trade_date=2026-03-17"


def _create_batch(session, source_name: str) -> IngestBatch:
    batch = IngestBatch(
        source_name=source_name,
        source_type="json",
        import_started_at=datetime.now(UTC).replace(tzinfo=None),
        import_finished_at=datetime.now(UTC).replace(tzinfo=None),
        total_rows=1,
        success_rows=1,
        failed_rows=0,
        status="completed",
        summary_json={},
    )
    session.add(batch)
    session.flush()
    return batch


def _add_snapshot_triplet(session, *, batch_id: int, symbol: str, trade_date_value: date) -> None:
    session.add(
        RawOptionSnapshot(
            trade_date=trade_date_value,
            symbol=symbol,
            raw_payload_json={"symbol": symbol, "trade_date": trade_date_value.isoformat()},
            batch_id=batch_id,
        ),
    )
    session.add(
        FeatureSnapshot(
            trade_date=trade_date_value,
            symbol=symbol,
            vol_imb=1.0,
            batch_id=batch_id,
        ),
    )
    session.add(
        SignalSnapshot(
            trade_date=trade_date_value,
            symbol=symbol,
            s_dir=12.5,
            s_vol=8.0,
            s_conf=74.0,
            s_pers=55.0,
            quadrant=Quadrant.BULLISH_EXPANSION,
            signal_label=SignalLabel.DIRECTIONAL_BIAS,
            event_regime=EarningsRegime.NEUTRAL,
            shift_flag=False,
            prob_tier=ProbabilityTier.HIGH,
            is_watchlist=True,
            batch_id=batch_id,
        ),
    )
