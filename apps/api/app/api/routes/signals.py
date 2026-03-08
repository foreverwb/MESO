from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.api_response import ApiMeta, ApiResponse
from app.schemas.history_schema import HistorySignalRecord, SymbolHistoryResponse
from app.services.history_service import HistoryService


router = APIRouter(tags=["signals"])


@router.get("/signals/{symbol}", response_model=ApiResponse[HistorySignalRecord])
def get_signal_for_symbol_and_date(
    session: Annotated[Session, Depends(get_db_session)],
    symbol: str = Path(..., min_length=1),
    trade_date: date = Query(...),
) -> ApiResponse[HistorySignalRecord]:
    signals = HistoryService(session).get_signals_for_date(trade_date)
    normalized_symbol = symbol.upper()
    signal = next(
        (item for item in signals.items if item.symbol.upper() == normalized_symbol),
        None,
    )
    if signal is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_found",
                "message": (
                    f"No signal was found for symbol={symbol} "
                    f"on trade_date={trade_date.isoformat()}"
                ),
            },
        )

    return ApiResponse(
        data=signal,
        meta=ApiMeta(count=1, trade_date=trade_date, symbol=signal.symbol),
    )


@router.get("/symbol-history/{symbol}", response_model=ApiResponse[SymbolHistoryResponse])
def get_symbol_history(
    session: Annotated[Session, Depends(get_db_session)],
    symbol: str = Path(..., min_length=1),
    lookback_days: int = Query(default=10, ge=1, le=90),
) -> ApiResponse[SymbolHistoryResponse]:
    history = HistoryService(session).get_symbol_history(symbol, lookback_days)
    if not history.items:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_found",
                "message": f"No history was found for symbol={symbol}",
            },
        )

    return ApiResponse(
        data=history,
        meta=ApiMeta(
            count=len(history.items),
            symbol=history.symbol,
            lookback_days=history.lookback_days,
        ),
    )
