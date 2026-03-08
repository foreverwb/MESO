from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.api_response import ApiMeta, ApiResponse, ChartPoint
from app.schemas.history_schema import (
    DateGroupSummary,
    DeletedTradeDateSummary,
    HistorySignalRecord,
    TrendConsistencyResponse,
)
from app.services.config_loader import ConfigLoader
from app.services.history_service import HistoryService


router = APIRouter(tags=["dashboard"])


@router.get("/date-groups", response_model=ApiResponse[list[DateGroupSummary]])
def get_date_groups(
    session: Annotated[Session, Depends(get_db_session)],
    limit: int | None = Query(default=None, ge=1, le=90),
) -> ApiResponse[list[DateGroupSummary]]:
    config_loader = ConfigLoader()
    effective_limit = limit or config_loader.get_ui().default_date_group_size_days
    date_groups = HistoryService(session).get_date_groups(limit=effective_limit)
    return ApiResponse(
        data=date_groups,
        meta=ApiMeta(count=len(date_groups), limit=effective_limit),
    )


@router.get("/chart-points", response_model=ApiResponse[list[ChartPoint]])
def get_chart_points(
    session: Annotated[Session, Depends(get_db_session)],
    trade_date: date = Query(...),
) -> ApiResponse[list[ChartPoint]]:
    history = HistoryService(session).get_signals_for_date(trade_date)
    if history.total_signals == 0:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_found",
                "message": f"No signals were found for trade_date={trade_date.isoformat()}",
            },
        )

    points = [_to_chart_point(item) for item in history.items]
    return ApiResponse(
        data=points,
        meta=ApiMeta(count=len(points), trade_date=trade_date),
    )


@router.get("/trend-consistency", response_model=ApiResponse[TrendConsistencyResponse])
def get_trend_consistency(
    session: Annotated[Session, Depends(get_db_session)],
    trade_date: date = Query(...),
    limit: int = Query(default=6, ge=1, le=12),
) -> ApiResponse[TrendConsistencyResponse]:
    history_service = HistoryService(session)
    history = history_service.get_signals_for_date(trade_date)
    if history.total_signals == 0:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_found",
                "message": f"No signals were found for trade_date={trade_date.isoformat()}",
            },
        )

    summary = history_service.get_trend_consistency(trade_date, limit=limit)
    count = len(summary.directional.overlap) + len(summary.volatility.overlap)
    return ApiResponse(
        data=summary,
        meta=ApiMeta(count=count, trade_date=trade_date, limit=limit),
    )


@router.delete("/date-groups/{trade_date}", response_model=ApiResponse[DeletedTradeDateSummary])
def delete_date_group(
    session: Annotated[Session, Depends(get_db_session)],
    trade_date: date,
) -> ApiResponse[DeletedTradeDateSummary]:
    try:
        summary = HistoryService(session).delete_trade_date(trade_date)
    except LookupError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_found",
                "message": str(exc),
            },
        ) from exc

    return ApiResponse(
        data=summary,
        meta=ApiMeta(trade_date=trade_date),
    )


def _to_chart_point(item: HistorySignalRecord) -> ChartPoint:
    bubble_inputs = [
        score
        for score in (item.s_conf, item.s_pers)
        if score is not None
    ]
    bubble_size = sum(bubble_inputs) / len(bubble_inputs) if bubble_inputs else 0.0
    return ChartPoint(
        symbol=item.symbol,
        trade_date=item.trade_date,
        x_score=item.s_dir or 0.0,
        y_score=item.s_vol or 0.0,
        bubble_size=bubble_size,
        quadrant=item.quadrant,
        signal_label=item.signal_label,
        s_conf=item.s_conf,
        s_pers=item.s_pers,
        highlight=item.is_watchlist,
    )
