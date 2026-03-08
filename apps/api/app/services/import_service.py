from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime
import json
from pathlib import Path
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import EarningsRegime, ProbabilityTier, Quadrant, SignalLabel
from app.db.models import IngestBatch
from app.repositories.batches import BatchCreate, BatchRepository
from app.repositories.raw_snapshots import RawSnapshotCreate, RawSnapshotRepository
from app.repositories.signal_snapshots import SignalSnapshotCreate, SignalSnapshotRepository
from app.schemas.history_schema import HistorySignalRecord
from app.schemas.import_schema import ImportRowError, ImportSummary, NormalizedImportRow
from app.services.classifier import ClassifiedSignalRecord, SignalClassifier
from app.services.config_loader import ConfigLoader
from app.services.cross_section_ranker import CrossSectionRanker
from app.services.feature_engine import FeatureEngine
from app.services.import_normalizer import ImportNormalizer
from app.services.scoring_engine import ScoringEngine
from app.services.shift_engine import ShiftEngine
from app.services.validators import FailedRecordValidation, validate_records


MONTH_LOOKUP = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAY": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OCT": 10,
    "NOV": 11,
    "DEC": 12,
}


@dataclass(frozen=True)
class PreparedSignalImportRow:
    row: NormalizedImportRow
    scoring_input: dict[str, Any]
    event_status: str


@dataclass(frozen=True)
class SignalImportRow:
    row: NormalizedImportRow
    payload: SignalSnapshotCreate


class ImportService:
    def __init__(self, session: Session, config_loader: ConfigLoader | None = None) -> None:
        self._session = session
        self._config_loader = config_loader or ConfigLoader()
        self._normalizer = ImportNormalizer(self._config_loader)
        self._batch_repository = BatchRepository(session)
        self._raw_repository = RawSnapshotRepository(session)
        self._signal_repository = SignalSnapshotRepository(session)
        self._feature_engine = FeatureEngine()
        self._cross_section_ranker = CrossSectionRanker(self._config_loader)
        self._scoring_engine = ScoringEngine(self._config_loader)
        self._classifier = SignalClassifier(self._config_loader)
        self._shift_engine = ShiftEngine()

    def import_file(
        self,
        file_path: str | Path,
        *,
        source_name: str | None = None,
        trade_date_override: date | None = None,
        ignore_unknown_fields: bool = False,
    ) -> ImportSummary:
        resolved_path = Path(file_path)
        source_type = self._detect_source_type(resolved_path)
        raw_rows = self._read_rows(resolved_path, source_type)
        return self.import_rows(
            raw_rows,
            source_name=source_name or resolved_path.name,
            source_type=source_type,
            trade_date_override=trade_date_override,
            ignore_unknown_fields=ignore_unknown_fields,
        )

    def import_rows(
        self,
        rows: list[dict[str, Any]],
        *,
        source_name: str,
        source_type: str,
        trade_date_override: date | None = None,
        ignore_unknown_fields: bool = False,
    ) -> ImportSummary:
        batch = self._create_batch(source_name=source_name, source_type=source_type)
        try:
            normalization_result = self._normalizer.normalize_rows(
                rows,
                trade_date_override=trade_date_override,
                ignore_unknown_fields=ignore_unknown_fields,
            )
            validation_result = validate_records(normalization_result.rows)
            validated_rows = [
                self._coerce_normalized_row(record)
                for record in validation_result.passed_records
            ]
            inserted_rows, insert_errors = self._insert_rows(
                batch_id=batch.id,
                normalized_rows=validated_rows,
            )
            signal_rows, signal_build_errors = self._build_signal_rows(
                batch_id=batch.id,
                normalized_rows=inserted_rows,
            )
            inserted_signal_rows, signal_insert_errors = self._insert_signal_rows(signal_rows)
            validation_errors = self._to_import_errors(validation_result.failed_records)
            errors = [
                *normalization_result.errors,
                *validation_errors,
                *insert_errors,
                *signal_build_errors,
                *signal_insert_errors,
            ]
            summary = ImportSummary(
                batch_id=batch.id,
                source_name=batch.source_name,
                source_type=source_type,
                total_rows=len(rows),
                success_rows=len(inserted_rows),
                signal_rows=inserted_signal_rows,
                failed_rows=len(errors),
                errors=errors,
            )
        except Exception as exc:
            self._session.rollback()
            summary = ImportSummary(
                batch_id=batch.id,
                source_name=batch.source_name,
                source_type=source_type,
                total_rows=0,
                success_rows=0,
                signal_rows=0,
                failed_rows=1,
                errors=[
                    ImportRowError(
                        row_number=0,
                        message=str(exc),
                        raw_payload={},
                    ),
                ],
            )

        self._update_batch(batch_id=batch.id, summary=summary)
        self._session.commit()
        return summary

    def _create_batch(self, *, source_name: str, source_type: str) -> IngestBatch:
        batch = self._batch_repository.create_batch(
            BatchCreate(
                source_name=source_name,
                source_type=source_type,
                import_started_at=self._utcnow(),
                status="running",
                summary_json={},
            ),
        )
        self._session.commit()
        return batch

    def _read_rows(self, file_path: Path, source_type: str) -> list[dict[str, Any]]:
        if source_type == "csv":
            return self._read_csv_rows(file_path)
        if source_type == "json":
            return self._read_json_rows(file_path)
        raise ValueError(f"Unsupported import source type: {source_type}")

    def _read_csv_rows(self, file_path: Path) -> list[dict[str, Any]]:
        with file_path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            if reader.fieldnames is None:
                raise ValueError("CSV import source must include a header row")
            return [dict(row) for row in reader]

    def _read_json_rows(self, file_path: Path) -> list[dict[str, Any]]:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("JSON import source must be an array of objects")
        if not all(isinstance(row, dict) for row in payload):
            raise ValueError("JSON import source must be an array of objects")
        return [dict(row) for row in payload]

    def _insert_rows(
        self,
        *,
        batch_id: int,
        normalized_rows: list[NormalizedImportRow],
    ) -> tuple[list[NormalizedImportRow], list[ImportRowError]]:
        if not normalized_rows:
            return [], []

        raw_rows = [self._to_repository_payload(row, batch_id=batch_id) for row in normalized_rows]
        try:
            with self._session.begin_nested():
                self._raw_repository.insert_raw_rows(raw_rows)
            return normalized_rows, []
        except IntegrityError:
            pass

        inserted_rows: list[NormalizedImportRow] = []
        errors: list[ImportRowError] = []

        for normalized_row, raw_row in zip(normalized_rows, raw_rows, strict=True):
            try:
                with self._session.begin_nested():
                    self._raw_repository.insert_raw_rows([raw_row])
                inserted_rows.append(normalized_row)
            except IntegrityError as exc:
                errors.append(
                    ImportRowError(
                        row_number=normalized_row.row_number,
                        message=f"Database integrity error: {exc.orig}",
                        raw_payload=normalized_row.raw_payload_json,
                    ),
                )

        return inserted_rows, errors

    def _build_signal_rows(
        self,
        *,
        batch_id: int,
        normalized_rows: list[NormalizedImportRow],
    ) -> tuple[list[SignalImportRow], list[ImportRowError]]:
        if not normalized_rows:
            return [], []

        errors: list[ImportRowError] = []
        prepared_rows: list[PreparedSignalImportRow] = []

        for row in normalized_rows:
            scoring_source = row.model_dump(mode="python", by_alias=True)
            scoring_source["batch_id"] = batch_id

            try:
                feature_record = self._feature_engine.build_feature_record(scoring_source)
            except Exception as exc:
                errors.append(
                    ImportRowError(
                        row_number=row.row_number,
                        message=f"Signal feature error: {exc}",
                        raw_payload=row.raw_payload_json,
                    ),
                )
                continue

            prepared_rows.append(
                PreparedSignalImportRow(
                    row=row,
                    scoring_input=scoring_source | feature_record.model_dump(mode="python"),
                    event_status=self._resolve_event_status(row.earnings, row.trade_date),
                ),
            )

        if not prepared_rows:
            return [], errors

        ranked_inputs = self._cross_section_ranker.rank_records(
            [prepared_row.scoring_input for prepared_row in prepared_rows],
        )

        classified_rows: list[tuple[NormalizedImportRow, ClassifiedSignalRecord]] = []
        for prepared_row, ranked_input in zip(prepared_rows, ranked_inputs, strict=True):
            try:
                scoring_record = self._scoring_engine.score_all(ranked_input)
                classified_record = self._classifier.classify(
                    scoring_record,
                    event_status=prepared_row.event_status,
                )
            except Exception as exc:
                errors.append(
                    ImportRowError(
                        row_number=prepared_row.row.row_number,
                        message=f"Signal classification error: {exc}",
                        raw_payload=prepared_row.row.raw_payload_json,
                    ),
                )
                continue

            classified_rows.append((prepared_row.row, classified_record))

        shift_flags = self._compute_shift_flags(classified_rows)

        signal_rows = [
            SignalImportRow(
                row=row,
                payload=SignalSnapshotCreate(
                    trade_date=classified_record.trade_date,
                    symbol=classified_record.symbol,
                    s_dir=classified_record.s_dir,
                    s_vol=classified_record.s_vol,
                    s_conf=classified_record.s_conf,
                    s_pers=classified_record.s_pers,
                    quadrant=Quadrant(classified_record.quadrant),
                    signal_label=SignalLabel(classified_record.signal_label),
                    event_regime=EarningsRegime(classified_record.event_regime),
                    shift_flag=shift_flags.get((classified_record.symbol, classified_record.trade_date), False),
                    prob_tier=self._to_probability_tier(classified_record.prob_tier),
                    is_watchlist=classified_record.is_watchlist,
                    batch_id=batch_id,
                ),
            )
            for row, classified_record in classified_rows
        ]

        return signal_rows, errors

    def _insert_signal_rows(
        self,
        rows: list[SignalImportRow],
    ) -> tuple[int, list[ImportRowError]]:
        if not rows:
            return 0, []

        payloads = [row.payload for row in rows]
        try:
            with self._session.begin_nested():
                self._signal_repository.insert_signal_rows(payloads)
            return len(payloads), []
        except IntegrityError:
            pass

        inserted_rows = 0
        errors: list[ImportRowError] = []

        for row in rows:
            try:
                with self._session.begin_nested():
                    self._signal_repository.insert_signal_rows([row.payload])
                inserted_rows += 1
            except IntegrityError as exc:
                errors.append(
                    ImportRowError(
                        row_number=row.row.row_number,
                        message=f"Signal snapshot integrity error: {exc.orig}",
                        raw_payload=row.row.raw_payload_json,
                    ),
                )

        return inserted_rows, errors

    def _to_repository_payload(
        self,
        row: NormalizedImportRow,
        *,
        batch_id: int,
    ) -> RawSnapshotCreate:
        payload = row.model_dump(mode="python")
        raw_payload_json = payload.pop("raw_payload_json")
        payload.pop("row_number", None)
        return RawSnapshotCreate(
            batch_id=batch_id,
            raw_payload_json=raw_payload_json,
            **payload,
        )

    def _coerce_normalized_row(self, row: NormalizedImportRow | dict[str, Any]) -> NormalizedImportRow:
        if isinstance(row, NormalizedImportRow):
            return row
        return NormalizedImportRow.model_validate(row)

    def _to_import_errors(
        self,
        failed_records: list[FailedRecordValidation],
    ) -> list[ImportRowError]:
        import_errors: list[ImportRowError] = []
        for failed_record in failed_records:
            for issue in failed_record.errors:
                import_errors.append(
                    ImportRowError(
                        row_number=issue.row_index or failed_record.row_index or 0,
                        message=(
                            f"field={issue.field}; "
                            f"raw_value={issue.raw_value!r}; "
                            f"reason={issue.reason}"
                        ),
                        raw_payload=failed_record.record.get("raw_payload_json", {}),
                    ),
                )
        return import_errors

    def _update_batch(self, *, batch_id: int, summary: ImportSummary) -> None:
        batch = self._session.get(IngestBatch, batch_id)
        if batch is None:
            raise RuntimeError(f"Ingest batch {batch_id} was not found")

        batch.import_finished_at = self._utcnow()
        batch.total_rows = summary.total_rows
        batch.success_rows = summary.success_rows
        batch.failed_rows = summary.failed_rows
        batch.status = "completed" if summary.failed_rows == 0 else "completed_with_errors"
        batch.summary_json = summary.model_dump(mode="json")

    def _compute_shift_flags(
        self,
        classified_rows: list[tuple[NormalizedImportRow, ClassifiedSignalRecord]],
    ) -> dict[tuple[str, date], bool]:
        grouped_records: dict[str, list[HistorySignalRecord]] = {}
        shift_flags: dict[tuple[str, date], bool] = {}

        for _, classified_record in classified_rows:
            grouped_records.setdefault(classified_record.symbol, []).append(
                HistorySignalRecord(
                    trade_date=classified_record.trade_date,
                    symbol=classified_record.symbol,
                    batch_id=classified_record.batch_id or 0,
                    s_dir=classified_record.s_dir,
                    s_vol=classified_record.s_vol,
                    s_conf=classified_record.s_conf,
                    s_pers=classified_record.s_pers,
                    quadrant=classified_record.quadrant,
                    signal_label=classified_record.signal_label,
                    event_regime=classified_record.event_regime,
                    prob_tier=classified_record.prob_tier,
                    is_watchlist=classified_record.is_watchlist,
                ),
            )

        for symbol, records in grouped_records.items():
            for evaluated_record in self._shift_engine.evaluate(records):
                shift_flags[(symbol, evaluated_record.trade_date)] = evaluated_record.shift_state != "none"

        return shift_flags

    def _detect_source_type(self, file_path: Path) -> str:
        suffix = file_path.suffix.lower()
        if suffix == ".csv":
            return "csv"
        if suffix == ".json":
            return "json"
        raise ValueError(f"Unsupported import source type for file: {file_path.name}")

    def _resolve_event_status(self, raw_earnings: Any, trade_date: date) -> str:
        earnings_date = self._parse_earnings_date(raw_earnings)
        if earnings_date is None:
            return "none"
        if earnings_date == trade_date:
            return "today"
        if earnings_date > trade_date:
            return "future"
        return "previous"

    def _parse_earnings_date(self, raw_earnings: Any) -> date | None:
        if not isinstance(raw_earnings, str):
            return None

        normalized_text = raw_earnings.strip()
        if not normalized_text:
            return None

        date_token = normalized_text.split()[0]
        parts = date_token.split("-")
        if len(parts) != 3:
            return None

        day_text, month_text, year_text = parts
        month_value = MONTH_LOOKUP.get(month_text.upper())
        if month_value is None:
            return None

        try:
            return date(int(year_text), month_value, int(day_text))
        except ValueError:
            return None

    def _to_probability_tier(self, value: str) -> ProbabilityTier:
        if value == "mid":
            return ProbabilityTier.MEDIUM
        return ProbabilityTier(value)

    def _utcnow(self) -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)
