"""Asynchronous QA grid orchestration helpers."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session, selectinload

from database import SessionLocal
from models.rag_grid import RagGridCell, RagGridJob
from parse.celery_app import app as celery_app
from schemas.api.rag_v2 import (
    EvidenceSchema,
    RagGridCellResponse,
    RagGridJobResponse,
    RagGridRequest,
    RagGridResponse,
    RagQueryFiltersSchema,
    RagQueryRequest,
    RagWarningSchema,
)
from services import rag_pipeline
from services.rag_shared import safe_float

JOB_STATUS_PENDING = "pending"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"

CELL_STATUS_PENDING = "pending"
CELL_STATUS_RUNNING = "running"
CELL_STATUS_OK = "ok"
CELL_STATUS_ERROR = "error"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _serialize_cell(cell: RagGridCell) -> RagGridCellResponse:
    evidence_payload = []
    for entry in cell.evidence or []:
        try:
            evidence_payload.append(EvidenceSchema(**entry))
        except Exception:
            continue
    return RagGridCellResponse(
        ticker=cell.ticker,
        question=cell.question,
        status=cell.status if cell.status in {CELL_STATUS_OK, CELL_STATUS_ERROR, CELL_STATUS_PENDING, CELL_STATUS_RUNNING} else CELL_STATUS_PENDING,
        answer=cell.answer,
        evidence=evidence_payload,
        error=cell.error,
        latencyMs=cell.latency_ms,
    )


def serialize_job(job: RagGridJob, *, include_cells: bool = True) -> RagGridJobResponse:
    cells: List[RagGridCellResponse] = []
    if include_cells:
        cells = [_serialize_cell(cell) for cell in sorted(job.cells, key=lambda c: (c.ticker, c.question))]
    return RagGridJobResponse(
        jobId=str(job.id),
        status=job.status,
        traceId=job.trace_id,
        totalCells=job.total_cells,
        completedCells=job.completed_cells,
        failedCells=job.failed_cells,
        results=cells,
        error=job.error,
        createdAt=job.created_at.isoformat() if job.created_at else None,
        updatedAt=job.updated_at.isoformat() if job.updated_at else None,
    )


def create_grid_job(db: Session, payload: RagGridRequest, *, requested_by: Optional[uuid.UUID]) -> RagGridJob:
    total_cells = len(payload.tickers) * len(payload.questions)
    if total_cells <= 0:
        raise ValueError("Grid payload must include at least one ticker and question.")

    job = RagGridJob(
        status=JOB_STATUS_PENDING,
        trace_id=str(uuid.uuid4()),
        requested_by=requested_by,
        ticker_count=len(payload.tickers),
        question_count=len(payload.questions),
        total_cells=total_cells,
        payload=payload.model_dump(mode="json"),
    )
    db.add(job)
    db.flush()
    for ticker in payload.tickers:
        for question in payload.questions:
            cell = RagGridCell(
                job_id=job.id,
                ticker=ticker,
                question=question,
                status=CELL_STATUS_PENDING,
            )
            db.add(cell)
    db.commit()
    db.refresh(job)
    return job


def enqueue_grid_job(job_id: uuid.UUID) -> None:
    celery_app.send_task("rag.grid.run_job", args=[str(job_id)])


def get_grid_job(db: Session, job_id: uuid.UUID, *, include_cells: bool = True) -> RagGridJob:
    query = db.query(RagGridJob)
    if include_cells:
        query = query.options(selectinload(RagGridJob.cells))
    job = query.filter(RagGridJob.id == job_id).first()
    if not job:
        raise ValueError("grid_job_not_found")
    return job


def _reset_cells(job: RagGridJob) -> None:
    for cell in job.cells:
        cell.status = CELL_STATUS_PENDING
        cell.answer = None
        cell.evidence = []
        cell.warnings = []
        cell.error = None
        cell.latency_ms = None
        cell.updated_at = _now()


def start_grid_job(job_id: str) -> None:
    with SessionLocal() as db:
        job = (
            db.query(RagGridJob)
            .options(selectinload(RagGridJob.cells))
            .filter(RagGridJob.id == uuid.UUID(job_id))
            .with_for_update()
            .first()
        )
        if not job:
            return
        if job.status not in {JOB_STATUS_PENDING, JOB_STATUS_FAILED}:
            return
        job.status = JOB_STATUS_RUNNING
        job.error = None
        job.completed_cells = 0
        job.failed_cells = 0
        job.updated_at = _now()
        _reset_cells(job)
        db.commit()

        for cell in job.cells:
            celery_app.send_task("rag.grid.process_cell", args=[str(cell.id)])


def _build_cell_request(job_payload: Dict[str, Any], *, question: str, ticker: str, top_k_override: Optional[int]) -> RagQueryRequest:
    filters_payload = job_payload.get("filters") or {}
    try:
        filters = RagQueryFiltersSchema(**filters_payload)
    except Exception:
        filters = RagQueryFiltersSchema()

    return RagQueryRequest(
        query=question,
        tickers=[ticker],
        topK=top_k_override or job_payload.get("topK") or 4,
        sourceTypes=job_payload.get("sourceTypes") or ["filing", "news", "event"],
        filters=filters,
    )


def _update_job_completion(job: RagGridJob) -> None:
    total_done = job.completed_cells + job.failed_cells
    if total_done >= job.total_cells:
        job.status = JOB_STATUS_FAILED if job.failed_cells else JOB_STATUS_COMPLETED
        job.updated_at = _now()


def process_grid_cell(cell_id: str) -> None:
    with SessionLocal() as db:
        cell = (
            db.query(RagGridCell)
            .options(selectinload(RagGridCell.job))
            .filter(RagGridCell.id == uuid.UUID(cell_id))
            .with_for_update()
            .first()
        )
        if not cell:
            return
        job = cell.job
        if job.status not in {JOB_STATUS_PENDING, JOB_STATUS_RUNNING}:
            return

        job.status = JOB_STATUS_RUNNING
        cell.status = CELL_STATUS_RUNNING
        cell.updated_at = _now()
        db.commit()

        started = time.perf_counter()
        try:
            request = _build_cell_request(job.payload or {}, question=cell.question, ticker=cell.ticker, top_k_override=None)
            result = rag_pipeline.run_rag_query(db, request)
            cell.status = CELL_STATUS_OK
            cell.answer = None
            cell.evidence = [item.model_dump(mode="json", exclude_none=True) for item in result.evidence]
            cell.warnings = [warning.model_dump(mode="json", exclude_none=True) for warning in result.warnings]
            cell.error = result.warnings[0].message if result.warnings else None
            cell.latency_ms = int((time.perf_counter() - started) * 1000)
            job.completed_cells += 1
        except Exception as exc:  # pragma: no cover - defensive guard
            cell.status = CELL_STATUS_ERROR
            cell.error = str(exc)
            cell.evidence = []
            cell.warnings = []
            cell.latency_ms = int((time.perf_counter() - started) * 1000)
            job.failed_cells += 1
            job.error = f"grid_cell_failed:{cell.id}"
        finally:
            cell.updated_at = _now()
            job.updated_at = _now()
            _update_job_completion(job)
            db.commit()


def run_grid(
    db: Session,
    payload: RagGridRequest,
) -> RagGridResponse:
    """Execute a synchronous grid request (ticker × question)."""

    cells: List[RagGridCellResponse] = []
    trace_id = str(uuid.uuid4())
    for ticker in payload.tickers:
        for question in payload.questions:
            started = time.perf_counter()
            request = RagQueryRequest(
                query=question,
                tickers=[ticker],
                topK=payload.topK,
                filters=payload.filters,
            )
            try:
                result = rag_pipeline.run_rag_query(db, request)
                latency_ms = int((time.perf_counter() - started) * 1000)
                warning_text = result.warnings[0].message if result.warnings else None
                cells.append(
                    RagGridCellResponse(
                        ticker=ticker,
                        question=question,
                        status="ok" if result.evidence else "pending",
                        answer=None,
                        evidence=result.evidence,
                        error=warning_text,
                        latencyMs=latency_ms,
                    )
                )
            except Exception as exc:  # pragma: no cover - defensive path
                latency_ms = int((time.perf_counter() - started) * 1000)
                cells.append(
                    RagGridCellResponse(
                        ticker=ticker,
                        question=question,
                        status="error",
                        evidence=[],
                        error=str(exc),
                        latencyMs=latency_ms,
                    )
                )
    return RagGridResponse(results=cells, traceId=trace_id)


__all__ = [
    "create_grid_job",
    "enqueue_grid_job",
    "get_grid_job",
    "process_grid_cell",
    "run_grid",
    "serialize_job",
    "start_grid_job",
]
