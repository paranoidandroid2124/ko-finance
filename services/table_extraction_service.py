"""Persistence + orchestration layer for PDF table extraction."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy.orm import Session

from core.env import env_bool, env_int, env_str
from core.logging import get_logger
from models.filing import Filing
from models.table_extraction import TableCell, TableMeta
from parse.table_extraction import TableExtractionResult, TableExtractor, TableExtractorError
from parse.chunk_utils import build_chunk
from services.table_metrics import record_table_cell_accuracy, record_table_extract_success_ratio

logger = get_logger(__name__)

_DEFAULT_TYPES = tuple(
    token.strip()
    for token in (env_str("TABLE_EXTRACTION_TARGET_TYPES", "dividend,treasury,cb_bw,financials") or "").split(",")
    if token.strip()
)
_MAX_PAGES = env_int("TABLE_EXTRACTION_MAX_PAGES", 30, minimum=1)
_MAX_TABLES = env_int("TABLE_EXTRACTION_MAX_TABLES", 80, minimum=1)
_TIME_BUDGET = env_int("TABLE_EXTRACTION_TAT_SECONDS", 15, minimum=5)
_WRITE_ARTIFACTS = env_bool("TABLE_EXTRACTION_WRITE_ARTIFACTS", True)
_INCLUDE_UNKNOWN = env_bool("TABLE_EXTRACTION_INCLUDE_UNKNOWN", False)

_OUTPUT_DIR = Path(env_str("TABLE_EXTRACTION_OUTPUT_DIR", "reports/table_extraction") or "reports/table_extraction")
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class TableExtractionServiceError(RuntimeError):
    """Raised when the orchestrator fails to complete a run."""


def _artifact_dir(receipt_no: Optional[str]) -> Path:
    slug = receipt_no or "unknown"
    target = _OUTPUT_DIR / slug
    target.mkdir(parents=True, exist_ok=True)
    return target


def _write_artifacts(receipt_no: Optional[str], result: TableExtractionResult) -> Dict[str, str]:
    directory = _artifact_dir(receipt_no)
    base = directory / f"page{result.page_number:03d}_table{result.table_index:02d}"
    html_path = base.with_suffix(".html")
    csv_path = base.with_suffix(".csv")
    json_path = base.with_suffix(".json")

    try:
        html_path.write_text(result.html, encoding="utf-8")
        csv_path.write_text(result.csv, encoding="utf-8")
        json_path.write_text(json.dumps(result.json_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:  # pragma: no cover - filesystem guard
        logger.warning("Failed to persist table artifacts at %s: %s", directory, exc)
        return {}

    return {
        "html": str(html_path),
        "csv": str(csv_path),
        "json": str(json_path),
    }


def _filter_results(results: Sequence[TableExtractionResult]) -> List[TableExtractionResult]:
    if not _DEFAULT_TYPES and _INCLUDE_UNKNOWN:
        return list(results)
    if _DEFAULT_TYPES and _INCLUDE_UNKNOWN:
        return list(results)
    if not _DEFAULT_TYPES:
        return [result for result in results if result.table_type != "unknown"]
    return [result for result in results if result.table_type in _DEFAULT_TYPES]


def _normalize_markdown_cell(value: str) -> str:
    if not value:
        return ""
    sanitized = value.replace("\n", " ").strip()
    return sanitized.replace("|", "\\|")


def _build_markdown_table(result: TableExtractionResult) -> Optional[str]:
    header_paths = result.header_paths or []
    headers: List[str] = []
    if header_paths:
        for idx, path in enumerate(header_paths):
            label = " / ".join([entry for entry in path if entry]) or f"Column {idx + 1}"
            headers.append(_normalize_markdown_cell(label))
    elif result.json_payload.get("headerRows"):
        headers = [
            _normalize_markdown_cell(cell)
            for cell in result.json_payload["headerRows"][0]
        ]

    column_count = result.stats.get("columnCount") or len(headers)
    if column_count <= 0:
        body_width = len(result.json_payload.get("bodyRows", [[]])[0]) if result.json_payload.get("bodyRows") else 0
        column_count = max(body_width, 1)
    if not headers:
        headers = [f"Column {idx + 1}" for idx in range(column_count)]

    table_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]

    body_rows = result.json_payload.get("bodyRows") or []
    if not body_rows:
        body_rows = result.body_rows

    for row in body_rows:
        normalized_row = [_normalize_markdown_cell(cell) for cell in row]
        if len(normalized_row) < len(headers):
            normalized_row.extend([""] * (len(headers) - len(normalized_row)))
        elif len(normalized_row) > len(headers):
            normalized_row = normalized_row[: len(headers)]
        table_lines.append("| " + " | ".join(normalized_row) + " |")

    return "\n".join(table_lines) if len(table_lines) > 2 else None


def _build_table_chunk(
    filing: Filing,
    meta: TableMeta,
    result: TableExtractionResult,
    markdown_table: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not markdown_table:
        return None
    header = result.title or result.table_type or "Extracted Table"
    table_text = (
        f"{header} (Page {result.page_number}, Index {result.table_index})\n\n{markdown_table}"
    )
    chunk_id = f"table:{filing.id}:{result.page_number}:{result.table_index}"
    metadata = {
        "table_type": result.table_type,
        "page_number": result.page_number,
        "table_index": result.table_index,
        "table_id": str(meta.id),
        "receipt_no": filing.receipt_no,
        "corp_code": filing.corp_code,
        "ticker": filing.ticker,
        "source": "table_extraction",
    }
    return build_chunk(
        chunk_id,
        chunk_type="table",
        content=table_text,
        section="tables",
        source="table_extraction",
        page_number=result.page_number,
        metadata=metadata,
    )


def _persist_table(
    db: Session,
    filing: Filing,
    pdf_path: str,
    result: TableExtractionResult,
    *,
    artifacts: Optional[Dict[str, str]] = None,
) -> TableMeta:
    table_meta = TableMeta(
        id=uuid.uuid4(),
        filing_id=filing.id,
        receipt_no=filing.receipt_no,
        corp_code=filing.corp_code,
        corp_name=filing.corp_name,
        ticker=filing.ticker,
        table_type=result.table_type,
        table_title=result.title,
        page_number=result.page_number,
        table_index=result.table_index,
        header_rows=result.stats.get("headerRows", 0),
        row_count=result.stats.get("rowCount", 0),
        column_count=result.stats.get("columnCount", 0),
        non_empty_cells=result.stats.get("nonEmptyCells", 0),
        confidence=result.confidence,
        latency_ms=int(result.duration_ms),
        checksum=result.checksum,
        column_headers=result.header_paths,
        quality=result.stats,
        table_json=result.json_payload,
        html=result.html,
        csv=result.csv,
        extra={
            "matchedKeywords": result.matched_keywords,
            "bbox": list(result.bbox),
            "artifacts": artifacts,
            "sourcePdf": pdf_path,
        },
    )
    db.add(table_meta)
    db.flush()

    for cell in result.cells:
        db.add(
            TableCell(
                table_id=table_meta.id,
                row_index=cell.row_index,
                column_index=cell.column_index,
                header_path=cell.header_path,
                raw_value=cell.raw_value,
                normalized_value=cell.normalized_value,
                numeric_value=cell.numeric_value,
                value_type=cell.value_type,
                confidence=cell.confidence,
            )
        )

    return table_meta


def extract_tables_for_filing(
    db: Session,
    *,
    filing: Filing,
    pdf_path: str,
    max_pages: Optional[int] = None,
    max_tables: Optional[int] = None,
    time_budget_seconds: Optional[int] = None,
    source: str = "ingest",
) -> Dict[str, Any]:
    """Run the PDF table extractor and persist normalized results."""

    if not pdf_path:
        raise TableExtractionServiceError("PDF path is empty.")
    if not Path(pdf_path).is_file():
        raise TableExtractionServiceError(f"PDF not found at {pdf_path}")

    started = time.perf_counter()
    extractor = TableExtractor(
        target_types=_DEFAULT_TYPES or None,
        max_pages=max_pages or _MAX_PAGES,
        max_tables=max_tables or _MAX_TABLES,
        time_budget_seconds=float(time_budget_seconds or _TIME_BUDGET),
    )

    try:
        raw_results = extractor.extract(pdf_path)
    except TableExtractorError as exc:
        raise TableExtractionServiceError(str(exc)) from exc

    filtered_results = _filter_results(raw_results)
    logger.info(
        "table_extraction.results",
        extra={
            "filing_id": str(filing.id),
            "receipt_no": filing.receipt_no,
            "detected_tables": len(raw_results),
            "persisted_tables": len(filtered_results),
            "pdf_path": pdf_path,
        },
    )

    deleted = (
        db.query(TableMeta)
        .filter(TableMeta.filing_id == filing.id)
        .delete(synchronize_session=False)
    )
    db.flush()

    stored = 0
    chunk_payloads: List[Dict[str, Any]] = []
    for result in filtered_results:
        artifacts = _write_artifacts(filing.receipt_no, result) if _WRITE_ARTIFACTS else None
        table_meta = _persist_table(db, filing, pdf_path, result, artifacts=artifacts)
        stored += 1
        markdown_table = _build_markdown_table(result)
        chunk_entry = _build_table_chunk(filing, table_meta, result, markdown_table)
        if chunk_entry:
            chunk_payloads.append(chunk_entry)
        try:
            accuracy = float(result.stats.get("nonEmptyRatio", 0.0))
        except (TypeError, ValueError):
            accuracy = 0.0
        record_table_cell_accuracy(result.table_type or "unknown", accuracy)

    db.commit()

    record_table_extract_success_ratio(
        stored=stored,
        total=len(raw_results),
        source=source or "ingest",
    )

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return {
        "stored": stored,
        "discarded": len(raw_results) - stored,
        "deleted": deleted,
        "elapsed_ms": round(elapsed_ms, 2),
        "chunks": chunk_payloads,
    }


def run_table_extraction_for_receipt(db: Session, receipt_no: str, *, pdf_path: Optional[str] = None) -> Dict[str, Any]:
    """Convenience wrapper used by the CLI for ad-hoc reprocessing."""

    filing = (
        db.query(Filing)
        .filter(Filing.receipt_no == receipt_no)
        .one_or_none()
    )
    if not filing:
        raise TableExtractionServiceError(f"Filing with receipt_no={receipt_no} not found.")

    target_pdf = pdf_path or filing.file_path
    if not target_pdf:
        raise TableExtractionServiceError(f"Filing {receipt_no} does not have a resolved PDF path.")
    return extract_tables_for_filing(db, filing=filing, pdf_path=target_pdf, source="backfill")


__all__ = [
    "extract_tables_for_filing",
    "run_table_extraction_for_receipt",
    "TableExtractionServiceError",
]
