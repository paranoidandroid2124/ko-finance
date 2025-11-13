"""Structured table extractor for DART PDF filings."""

from __future__ import annotations

import csv
import hashlib
import html
import io
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import fitz  # type: ignore[import]

from core.logging import get_logger
from parse.chunk_utils import normalize_text

logger = get_logger(__name__)

NUMERIC_PUNCTUATION = {",", " ", "\u00a0"}
DATE_SEPARATORS = {".", "-", "/"}

_FULLWIDTH_DIGITS = {
    ord("０"): "0",
    ord("１"): "1",
    ord("２"): "2",
    ord("３"): "3",
    ord("４"): "4",
    ord("５"): "5",
    ord("６"): "6",
    ord("７"): "7",
    ord("８"): "8",
    ord("９"): "9",
}
_SPECIAL_DASHES = {
    ord("–"): "-",
    ord("—"): "-",
    ord("−"): "-",
    ord("﹣"): "-",
    ord("－"): "-",
}
_NUMERIC_TRANSLATION = {**_FULLWIDTH_DIGITS, **_SPECIAL_DASHES}

UNIT_KEYWORDS = {
    "억원": 1e8,
    "억 원": 1e8,
    "백만원": 1e6,
    "백만 원": 1e6,
    "천만원": 1e7,
    "천만 원": 1e7,
    "천원": 1e3,
    "천 원": 1e3,
    "원": 1.0,
}
DATE_REGEXPS = [
    re.compile(r"\d{4}[-./]?\d{1,2}[-./]?\d{1,2}"),
    re.compile(r"\d{2}[-./]\d{1,2}[-./]\d{1,2}"),
    re.compile(r"\d{4}\.?\s?Q[1-4]"),
]

TABLE_TYPE_KEYWORDS: Dict[str, Sequence[str]] = {
    "dividend": ("배당", "주당", "현금배당", "배당금", "cash dividend", "dividend"),
    "treasury": ("자사주", "취득", "처분", "소각", "buyback", "treasury", "capital outflow"),
    "cb_bw": ("전환사채", "cb", "bw", "신주인수권부", "convertible bond", "bond with warrant"),
    "financials": (
        "재무상태표",
        "손익계산서",
        "포괄손익",
        "현금흐름표",
        "balance sheet",
        "income statement",
        "cash flow",
    ),
}


@dataclass(slots=True)
class TableCellPayload:
    row_index: int
    column_index: int
    header_path: List[str]
    raw_value: str
    normalized_value: str
    numeric_value: Optional[float]
    value_type: str
    confidence: float


@dataclass(slots=True)
class TableExtractionResult:
    page_number: int
    table_index: int
    bbox: Tuple[float, float, float, float]
    header_rows: List[List[str]]
    body_rows: List[List[str]]
    header_paths: List[List[str]]
    table_type: str
    matched_keywords: List[str]
    title: str
    confidence: float
    stats: Dict[str, Any]
    html: str
    csv: str
    json_payload: Dict[str, Any]
    cells: List[TableCellPayload]
    checksum: str
    duration_ms: float


class TableExtractorError(RuntimeError):
    """Raised when table extraction fails unexpectedly."""


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if math.isnan(value) or math.isinf(value):
            return ""
        return f"{value}"
    text = normalize_text(str(value))
    return text.strip()


def _translate_numeric(text: str) -> str:
    if not text:
        return ""
    normalized = text.translate(_NUMERIC_TRANSLATION)
    normalized = normalized.replace("\u00a0", " ")
    return normalized


def _normalize_matrix(rows: Sequence[Sequence[Any]]) -> List[List[str]]:
    width = max((len(row) for row in rows if row), default=0)
    normalized: List[List[str]] = []
    for raw_row in rows:
        padded = list(raw_row) + [""] * (width - len(raw_row))
        normalized.append([_clean_value(cell) for cell in padded])
    return normalized


def _looks_numeric(value: str) -> bool:
    if not value:
        return False
    candidate = _translate_numeric(value).strip().lower()
    if candidate.endswith("%"):
        candidate = candidate[:-1]
    candidate = ''.join(ch for ch in candidate if ch not in NUMERIC_PUNCTUATION)
    if not candidate:
        return False
    if candidate.startswith("(") and candidate.endswith(")"):
        candidate = f"-{candidate[1:-1]}"
    try:
        float(candidate)
        return True
    except ValueError:
        return False

def _parse_numeric(value: str) -> Optional[float]:
    if not _looks_numeric(value):
        return None
    candidate = _translate_numeric(value).strip().lower()
    sign = 1.0
    if candidate.startswith("(") and candidate.endswith(")"):
        sign = -1.0
        candidate = candidate[1:-1]
    suffix = 1.0
    if candidate.endswith("%"):
        suffix = 0.01
        candidate = candidate[:-1]
    unit_scale = 1.0
    for keyword, scale in UNIT_KEYWORDS.items():
        if keyword in candidate:
            unit_scale = scale
            candidate = candidate.replace(keyword, '')
            break
    cleaned = ''.join(ch for ch in candidate if ch not in NUMERIC_PUNCTUATION | {"%"}).replace("--", "-")
    if not cleaned:
        return None
    try:
        return float(cleaned) * sign * suffix * unit_scale
    except ValueError:
        return None

def _looks_date(value: str) -> bool:
    if not value:
        return False
    normalized = _translate_numeric(value).strip()
    if len(normalized) < 6:
        return False
    for pattern in DATE_REGEXPS:
        if pattern.search(normalized):
            return True
    separators = sum(1 for ch in normalized if ch in DATE_SEPARATORS)
    digits = sum(1 for ch in normalized if ch.isdigit())
    return separators >= 1 and digits >= max(4, len(normalized) - separators)

def _row_is_data(row: Sequence[str]) -> bool:
    values = [cell for cell in row if cell]
    if not values:
        return False
    numeric = sum(1 for cell in values if _looks_numeric(cell))
    if numeric >= max(1, len(values) // 2):
        return True
    dateish = sum(1 for cell in values if _looks_date(cell))
    return (numeric + dateish) >= max(1, len(values) // 2)


def _detect_header_rows(rows: Sequence[Sequence[str]]) -> int:
    if not rows:
        return 0
    header_rows = 0
    max_header_candidates = min(len(rows), 4)
    for idx in range(max_header_candidates):
        row = rows[idx]
        if not any(row):
            continue
        if _row_is_data(row) and header_rows > 0:
            break
        if _row_is_data(row) and header_rows == 0:
            # If the very first row already looks like data, use it as header for safety.
            header_rows = 1
            break
        header_rows = idx + 1
    return max(1, header_rows)


def _fill_header_matrix(rows: Sequence[Sequence[str]], width: int) -> List[List[str]]:
    matrix: List[List[str]] = []
    for row in rows:
        padded = list(row) + [""] * (width - len(row))
        carried: List[str] = []
        last = ""
        for cell in padded:
            normalized = cell.strip()
            if normalized:
                last = normalized
                carried.append(normalized)
            else:
                carried.append(last)
        matrix.append(carried)

    for col in range(width):
        last_value = ""
        for row_idx, row in enumerate(matrix):
            cell = row[col]
            if cell:
                last_value = cell
            else:
                row[col] = last_value
    return matrix


def _build_header_paths(header_matrix: Sequence[Sequence[str]]) -> List[List[str]]:
    if not header_matrix:
        return []
    width = len(header_matrix[0])
    paths: List[List[str]] = []
    for col in range(width):
        column_path = []
        for row in header_matrix:
            value = row[col].strip()
            if value:
                column_path.append(value)
        paths.append(column_path)
    return paths


def _value_type(value: str) -> str:
    if not value:
        return "empty"
    if _looks_numeric(value):
        return "number"
    if _looks_date(value):
        return "date"
    lowered = value.lower()
    if lowered in {"yes", "no", "true", "false"}:
        return "flag"
    return "text"


def _derive_title(header_rows: Sequence[Sequence[str]], header_paths: Sequence[Sequence[str]], page_number: int, table_index: int) -> str:
    for row in header_rows:
        joined = " ".join(cell for cell in row if cell).strip()
        if joined:
            return joined
    for path in header_paths:
        if path:
            return " / ".join(path)
    return f"Table {page_number}-{table_index}"


def _classify_table(text_tokens: Iterable[str]) -> Tuple[str, List[str], float]:
    joined = " ".join(token.lower() for token in text_tokens if token).strip()
    if not joined:
        return "unknown", [], 0.35
    best_type = "unknown"
    best_score = 0.35
    matched_keywords: List[str] = []
    for table_type, keywords in TABLE_TYPE_KEYWORDS.items():
        matches = [kw for kw in keywords if kw.lower() in joined]
        if not matches:
            continue
        score = min(0.95, 0.6 + (0.1 * len(matches)))
        if score > best_score:
            best_type = table_type
            best_score = score
            matched_keywords = matches
    return best_type, matched_keywords, best_score


def _build_html(header_rows: Sequence[Sequence[str]], body_rows: Sequence[Sequence[str]]) -> str:
    buffer: List[str] = ["<table class=\"kof-table\">"]
    if header_rows:
        buffer.append("<thead>")
        for row in header_rows:
            cells = "".join(f"<th>{html.escape(cell)}</th>" for cell in row)
            buffer.append(f"<tr>{cells}</tr>")
        buffer.append("</thead>")
    buffer.append("<tbody>")
    for row in body_rows:
        cells = "".join(f"<td>{html.escape(cell)}</td>" for cell in row)
        buffer.append(f"<tr>{cells}</tr>")
    buffer.append("</tbody></table>")
    return "".join(buffer)


def _build_csv(rows: Sequence[Sequence[str]]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    for row in rows:
        writer.writerow(row)
    return output.getvalue()


class TableExtractor:
    """Extract structured tables (HTML/CSV/JSON) from PDF documents."""

    def __init__(
        self,
        *,
        target_types: Optional[Sequence[str]] = None,
        max_pages: Optional[int] = None,
        max_tables: Optional[int] = None,
        time_budget_seconds: float = 90.0,
    ) -> None:
        self.target_types = tuple(t.strip() for t in (target_types or []) if t.strip())
        self.max_pages = max_pages
        self.max_tables = max_tables
        self.time_budget_seconds = max(5.0, time_budget_seconds)

    def extract(self, pdf_path: str) -> List[TableExtractionResult]:
        path = Path(pdf_path)
        if not path.is_file():
            raise TableExtractorError(f"PDF not found: {pdf_path}")

        started = time.perf_counter()
        results: List[TableExtractionResult] = []
        try:
            document = fitz.open(pdf_path)
        except Exception as exc:  # pragma: no cover - PyMuPDF runtime guard
            raise TableExtractorError(f"Unable to open PDF: {exc}") from exc

        try:
            for page_number, page in enumerate(document, start=1):
                if self.max_pages and page_number > self.max_pages:
                    break
                tables = page.find_tables()
                if not tables:
                    continue

                for table_index, table in enumerate(tables, start=1):
                    table_start = time.perf_counter()
                    raw = table.extract()
                    if not raw:
                        continue
                    matrix = _normalize_matrix(raw)
                    if not matrix or not any(any(cell for cell in row) for row in matrix):
                        continue

                    header_rows_count = _detect_header_rows(matrix)
                    header_rows = matrix[:header_rows_count]
                    body_rows = matrix[header_rows_count:] or []

                    header_matrix = _fill_header_matrix(header_rows, len(matrix[0]))
                    header_paths = _build_header_paths(header_matrix)

                    rows_for_csv = header_rows + body_rows
                    csv_payload = _build_csv(rows_for_csv)
                    html_payload = _build_html(header_rows, body_rows)

                    cell_payloads: List[TableCellPayload] = []
                    non_empty_cells = 0
                    numeric_cells = 0
                    for row_idx, row in enumerate(body_rows):
                        for col_idx, value in enumerate(row):
                            normalized = value
                            numeric_value = _parse_numeric(value)
                            vtype = _value_type(value)
                            if normalized:
                                non_empty_cells += 1
                            if numeric_value is not None:
                                numeric_cells += 1
                            header_path = header_paths[col_idx] if col_idx < len(header_paths) else []
                            confidence = 0.25
                            if normalized:
                                confidence += 0.5
                            if numeric_value is not None:
                                confidence += 0.2
                            cell_payloads.append(
                                TableCellPayload(
                                    row_index=row_idx,
                                    column_index=col_idx,
                                    header_path=header_path,
                                    raw_value=value,
                                    normalized_value=normalized,
                                    numeric_value=numeric_value,
                                    value_type=vtype,
                                    confidence=min(1.0, confidence),
                                )
                            )

                    total_cells = len(body_rows) * len(matrix[0]) if body_rows else 0
                    non_empty_ratio = (non_empty_cells / total_cells) if total_cells else 0.0
                    header_coverage = (
                        sum(1 for path in header_paths if path)
                        / len(header_paths)
                        if header_paths
                        else 0.0
                    )
                    numeric_ratio = (numeric_cells / total_cells) if total_cells else 0.0

                    text_tokens = []
                    for row in header_rows:
                        text_tokens.extend(row)
                    for row in body_rows[:3]:
                        text_tokens.extend(row)
                    table_type, matched_keywords, base_confidence = _classify_table(text_tokens)

                    if self.target_types and table_type not in self.target_types:
                        continue

                    title = _derive_title(header_rows, header_paths, page_number, table_index)
                    derived_confidence = min(
                        0.99,
                        max(
                            base_confidence,
                            0.5 + (0.2 * header_coverage) + (0.2 * non_empty_ratio) + (0.05 * numeric_ratio),
                        ),
                    )
                    bbox = tuple(float(coord) for coord in table.bbox)
                    stats = {
                        "rowCount": len(body_rows),
                        "columnCount": len(matrix[0]) if matrix else 0,
                        "headerRows": header_rows_count,
                        "nonEmptyCells": non_empty_cells,
                        "nonEmptyRatio": round(non_empty_ratio, 4),
                        "headerCoverage": round(header_coverage, 4),
                        "numericRatio": round(numeric_ratio, 4),
                    }
                    table_json = {
                        "headerRows": header_rows,
                        "bodyRows": body_rows,
                        "headerPaths": header_paths,
                        "bbox": list(bbox),
                        "metrics": stats,
                    }
                    checksum = hashlib.sha1(
                        repr(table_json).encode("utf-8", errors="ignore")
                    ).hexdigest()

                    duration_ms = (time.perf_counter() - table_start) * 1000.0

                    result = TableExtractionResult(
                        page_number=page_number,
                        table_index=table_index,
                        bbox=bbox,
                        header_rows=header_rows,
                        body_rows=body_rows,
                        header_paths=header_paths,
                        table_type=table_type,
                        matched_keywords=matched_keywords,
                        title=title,
                        confidence=round(derived_confidence, 4),
                        stats=stats,
                        html=html_payload,
                        csv=csv_payload,
                        json_payload=table_json,
                        cells=cell_payloads,
                        checksum=checksum,
                        duration_ms=duration_ms,
                    )
                    results.append(result)

                    if self.max_tables and len(results) >= self.max_tables:
                        return results
                elapsed = time.perf_counter() - started
                if elapsed >= self.time_budget_seconds:
                    logger.warning(
                        "Table extraction aborted for %s after %.2fs (time budget %.2fs).",
                        pdf_path,
                        elapsed,
                        self.time_budget_seconds,
                    )
                    break
        finally:
            document.close()
        return results


__all__ = [
    "TableExtractor",
    "TableExtractorError",
    "TableExtractionResult",
    "TableCellPayload",
]
