from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import IngestBatch


@dataclass(frozen=True)
class BatchCreate:
    source_name: str
    source_type: str
    import_started_at: datetime
    import_finished_at: datetime | None = None
    total_rows: int = 0
    success_rows: int = 0
    failed_rows: int = 0
    status: str = "started"
    summary_json: dict[str, Any] = field(default_factory=dict)


class BatchRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_batch(self, payload: BatchCreate) -> IngestBatch:
        batch = IngestBatch(
            source_name=payload.source_name,
            source_type=payload.source_type,
            import_started_at=payload.import_started_at,
            import_finished_at=payload.import_finished_at,
            total_rows=payload.total_rows,
            success_rows=payload.success_rows,
            failed_rows=payload.failed_rows,
            status=payload.status,
            summary_json=payload.summary_json,
        )
        self._session.add(batch)
        self._session.flush()
        return batch
