from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from app.core.enums import EarningsRegime, ProbabilityTier, Quadrant, SignalLabel
from app.db.models import IngestBatch, SignalSnapshot
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


def test_trend_consistency_groups_symbols_by_direction_and_volatility(client_with_db) -> None:
    client, session_factory = client_with_db

    with session_factory() as session:
        batch = _create_batch(session)
        dates = [
            date(2026, 3, 10),
            date(2026, 3, 11),
            date(2026, 3, 12),
            date(2026, 3, 13),
            date(2026, 3, 16),
            date(2026, 3, 17),
        ]
        series_by_symbol = {
            "TSLA": {
                "s_dir": [10.0, 20.0, 30.0, 40.0, 52.0, 70.0],
                "s_vol": [5.0, 8.0, 4.0, 9.0, 7.0, 6.0],
            },
            "QQQ": {
                "s_dir": [60.0, 50.0, 40.0, 30.0, 20.0, 10.0],
                "s_vol": [1.0, 3.0, 5.0, 4.0, 2.0, 6.0],
            },
            "AAPL": {
                "s_dir": [2.0, 4.0, 1.0, 3.0, 5.0, 4.0],
                "s_vol": [10.0, 18.0, 22.0, 28.0, 33.0, 40.0],
            },
            "SPY": {
                "s_dir": [9.0, 7.0, 11.0, 10.0, 12.0, 8.0],
                "s_vol": [70.0, 64.0, 60.0, 54.0, 48.0, 42.0],
            },
            "IWM": {
                "s_dir": [5.0, 8.0, 10.0, 6.0, 7.0, 9.0],
                "s_vol": [3.0, 6.0, 4.0, 5.0, 8.0, 7.0],
            },
        }

        for symbol, series in series_by_symbol.items():
            for trade_date_value, s_dir, s_vol in zip(dates, series["s_dir"], series["s_vol"], strict=True):
                _add_signal_snapshot(
                    session,
                    batch_id=batch.id,
                    symbol=symbol,
                    trade_date_value=trade_date_value,
                    s_dir=s_dir,
                    s_vol=s_vol,
                )

        session.commit()

    response = client.get("/api/v1/trend-consistency?trade_date=2026-03-17&limit=3")

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"] == {
        "count": 6,
        "limit": 3,
        "trade_date": "2026-03-17",
        "symbol": None,
        "lookback_days": None,
    }
    assert payload["data"] == {
        "trade_date": "2026-03-17",
        "directional": {
            "overlap": [
                {
                    "symbol": "TSLA",
                    "current_score": 70.0,
                    "delta_3d": 40.0,
                    "delta_5d": 60.0,
                    "trend": "up",
                },
                {
                    "symbol": "QQQ",
                    "current_score": 10.0,
                    "delta_3d": -30.0,
                    "delta_5d": -50.0,
                    "trend": "down",
                },
                {
                    "symbol": "AAPL",
                    "current_score": 4.0,
                    "delta_3d": 3.0,
                    "delta_5d": 2.0,
                    "trend": "up",
                },
            ],
            "delta_3d": [
                {
                    "symbol": "TSLA",
                    "current_score": 70.0,
                    "delta_3d": 40.0,
                    "delta_5d": 60.0,
                    "trend": "up",
                },
                {
                    "symbol": "QQQ",
                    "current_score": 10.0,
                    "delta_3d": -30.0,
                    "delta_5d": -50.0,
                    "trend": "down",
                },
                {
                    "symbol": "AAPL",
                    "current_score": 4.0,
                    "delta_3d": 3.0,
                    "delta_5d": 2.0,
                    "trend": "up",
                },
            ],
            "delta_5d": [
                {
                    "symbol": "TSLA",
                    "current_score": 70.0,
                    "delta_3d": 40.0,
                    "delta_5d": 60.0,
                    "trend": "up",
                },
                {
                    "symbol": "QQQ",
                    "current_score": 10.0,
                    "delta_3d": -30.0,
                    "delta_5d": -50.0,
                    "trend": "down",
                },
                {
                    "symbol": "IWM",
                    "current_score": 9.0,
                    "delta_3d": -1.0,
                    "delta_5d": 4.0,
                    "trend": "mixed",
                },
            ],
        },
        "volatility": {
            "overlap": [
                {
                    "symbol": "AAPL",
                    "current_score": 40.0,
                    "delta_3d": 18.0,
                    "delta_5d": 30.0,
                    "trend": "up",
                },
                {
                    "symbol": "SPY",
                    "current_score": 42.0,
                    "delta_3d": -18.0,
                    "delta_5d": -28.0,
                    "trend": "down",
                },
                {
                    "symbol": "IWM",
                    "current_score": 7.0,
                    "delta_3d": 3.0,
                    "delta_5d": 4.0,
                    "trend": "up",
                },
            ],
            "delta_3d": [
                {
                    "symbol": "AAPL",
                    "current_score": 40.0,
                    "delta_3d": 18.0,
                    "delta_5d": 30.0,
                    "trend": "up",
                },
                {
                    "symbol": "SPY",
                    "current_score": 42.0,
                    "delta_3d": -18.0,
                    "delta_5d": -28.0,
                    "trend": "down",
                },
                {
                    "symbol": "IWM",
                    "current_score": 7.0,
                    "delta_3d": 3.0,
                    "delta_5d": 4.0,
                    "trend": "up",
                },
            ],
            "delta_5d": [
                {
                    "symbol": "AAPL",
                    "current_score": 40.0,
                    "delta_3d": 18.0,
                    "delta_5d": 30.0,
                    "trend": "up",
                },
                {
                    "symbol": "SPY",
                    "current_score": 42.0,
                    "delta_3d": -18.0,
                    "delta_5d": -28.0,
                    "trend": "down",
                },
                {
                    "symbol": "QQQ",
                    "current_score": 6.0,
                    "delta_3d": 1.0,
                    "delta_5d": 5.0,
                    "trend": "up",
                },
            ],
        },
    }


def test_trend_consistency_returns_not_found_for_missing_trade_date(client_with_db) -> None:
    client, _ = client_with_db

    response = client.get("/api/v1/trend-consistency?trade_date=2026-03-17")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["message"] == "No signals were found for trade_date=2026-03-17"


def _create_batch(session) -> IngestBatch:
    batch = IngestBatch(
        source_name="trend-consistency.json",
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


def _add_signal_snapshot(
    session,
    *,
    batch_id: int,
    symbol: str,
    trade_date_value: date,
    s_dir: float,
    s_vol: float,
) -> None:
    session.add(
        SignalSnapshot(
            trade_date=trade_date_value,
            symbol=symbol,
            s_dir=s_dir,
            s_vol=s_vol,
            s_conf=74.0,
            s_pers=61.0,
            quadrant=Quadrant.BULLISH_EXPANSION,
            signal_label=SignalLabel.DIRECTIONAL_BIAS,
            event_regime=EarningsRegime.NEUTRAL,
            shift_flag=False,
            prob_tier=ProbabilityTier.HIGH,
            is_watchlist=False,
            batch_id=batch_id,
        ),
    )
