"""Extract structured content from PDF filings."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import hashlib

import fitz  # PyMuPDF

from parse.chunk_utils import build_chunk, normalize_text

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MIN_PARAGRAPH_LENGTH = 25
VERTICAL_GAP_TOLERANCE = 24.0
COLUMN_ALIGNMENT_TOLERANCE = 40.0
FOOTNOTE_PATTERN = re.compile(r"^(\(?\d+[\)\.]|\[\d+\]|[*†‡])\s+", re.IGNORECASE)
FOOTNOTE_Y_RATIO = 0.8


def _clamp_pct(value: float) -> float:
    return max(0.0, min(100.0, value))


def _enrich_metadata(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    page_width: float,
    page_height: float,
    base: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Return metadata dictionary with absolute and relative coordinates."""
    width = page_width or 1.0
    height = page_height or 1.0
    metadata = {
        "bbox": [float(x0), float(y0), float(x1), float(y1)],
        "page_width": float(width),
        "page_height": float(height),
        "x_start_pct": _clamp_pct((x0 / width) * 100.0 if width else 0.0),
        "x_end_pct": _clamp_pct((x1 / width) * 100.0 if width else 0.0),
        "y_start_pct": _clamp_pct((y0 / height) * 100.0 if height else 0.0),
        "y_end_pct": _clamp_pct((y1 / height) * 100.0 if height else 0.0),
    }
    if base:
        metadata.update(base)
    return metadata


def _sanitize_rect(rect: Any) -> List[float]:
    if hasattr(rect, "x0") and hasattr(rect, "y0") and hasattr(rect, "x1") and hasattr(rect, "y1"):
        return [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]
    if isinstance(rect, (list, tuple)) and len(rect) >= 4:
        return [float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])]
    return [0.0, 0.0, 0.0, 0.0]


def _sentence_hash(text: str) -> Optional[str]:
    normalized = normalize_text(text) if text else ""
    if not normalized:
        return None
    return hashlib.sha1(normalized.encode("utf-8", errors="ignore")).hexdigest()


def _table_to_text(table_data: List[List[str]]) -> str:
    lines: List[str] = []
    if not table_data:
        return ""

    header: Optional[List[str]] = None
    for row in table_data:
        sanitized = [normalize_text(cell) if isinstance(cell, str) else "" for cell in row]
        if not any(sanitized):
            continue

        if header is None:
            header = sanitized
            continue

        row_entries: List[str] = []
        for idx, value in enumerate(sanitized):
            if not value:
                continue
            key = ""
            if header and idx < len(header) and header[idx].strip():
                key = header[idx].strip()
            elif header is None:
                key = f"항목{idx + 1}"
            else:
                key = f"열{idx + 1}"
            row_entries.append(f"{key}: {value}")

        if not row_entries:
            row_entries.append(" ".join(filter(None, sanitized)))
        lines.append(" · ".join(row_entries))

    return "\n".join(lines)


def _build_block_info(block: Sequence[Any]) -> Dict[str, Any]:
    x0, y0, x1, y1, raw_text = block[:5]
    text = raw_text.strip()
    if not text:
        return {"x0": float(x0), "y0": float(y0), "x1": float(x1), "y1": float(y1), "body_lines": [], "footnote_lines": [], "block_index": block[5] if len(block) > 5 else None}

    lines = [normalize_text(line) for line in text.splitlines() if line.strip()]
    footnote_lines = [line for line in lines if FOOTNOTE_PATTERN.match(line)]
    body_lines = [line for line in lines if line not in footnote_lines]

    return {
        "x0": float(x0),
        "y0": float(y0),
        "x1": float(x1),
        "y1": float(y1),
        "body_lines": body_lines,
        "footnote_lines": footnote_lines,
        "block_index": block[5] if len(block) > 5 else None,
    }


def _should_merge(prev_block: Dict[str, Any], next_block: Dict[str, Any]) -> bool:
    if not prev_block["body_lines"] or not next_block["body_lines"]:
        return False
    vertical_gap = next_block["y0"] - prev_block["y1"]
    if vertical_gap < 0 or vertical_gap > VERTICAL_GAP_TOLERANCE:
        return False
    horizontal_shift = abs(prev_block["x0"] - next_block["x0"])
    return horizontal_shift <= COLUMN_ALIGNMENT_TOLERANCE


def extract_chunks(pdf_path: str) -> List[Dict[str, Any]]:
    """Return chunks of text/table/footnote/figure elements from a PDF."""
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    chunks: List[Dict[str, Any]] = []
    chunk_counter = 1

    try:
        document = fitz.open(pdf_path)
        logger.info("Parsing PDF '%s' (%d pages).", pdf_path, len(document))

        for page_index, page in enumerate(document):
            page_number = page_index + 1
            page_height = float(page.rect.height or 1.0)
            page_width = float(page.rect.width or 1.0)

            block_infos = [_build_block_info(block) for block in page.get_text("blocks")]

            pending_lines: List[str] = []
            pending_blocks: List[Any] = []
            pending_bbox = [float("inf"), float("inf"), 0.0, 0.0]
            current_span: Optional[Dict[str, Any]] = None
            page_char_cursor = 0

            def _allocate_char_span(text: str) -> Tuple[int, int]:
                nonlocal page_char_cursor
                safe_len = len(text or "")
                start = page_char_cursor
                end = start + safe_len
                page_char_cursor = end + (1 if safe_len else 0)
                return start, end

            def _reset_pending() -> None:
                nonlocal pending_lines, pending_blocks, pending_bbox, current_span
                pending_lines = []
                pending_blocks = []
                pending_bbox = [float("inf"), float("inf"), 0.0, 0.0]
                current_span = None

            def _flush_pending() -> None:
                nonlocal chunk_counter, pending_lines, pending_blocks, pending_bbox, current_span
                if not pending_lines:
                    return
                content = " ".join(pending_lines).strip()
                if not content:
                    _reset_pending()
                    return

                char_start, char_end = _allocate_char_span(content)
                base_meta: Dict[str, Any] = {
                    "block_indices": [idx for idx in pending_blocks if idx is not None],
                    "approx_char_length": len(content),
                    "char_start": char_start,
                    "char_end": char_end,
                }
                hash_value = _sentence_hash(content)
                if hash_value:
                    base_meta["sentence_hash"] = hash_value
                metadata = _enrich_metadata(
                    pending_bbox[0],
                    pending_bbox[1],
                    pending_bbox[2],
                    pending_bbox[3],
                    page_width=page_width,
                    page_height=page_height,
                    base=base_meta,
                )
                chunks.append(
                    build_chunk(
                        f"pdf-text-{page_number}-{chunk_counter}",
                        chunk_type="text",
                        content=content,
                        section="body",
                        source="pdf",
                        page_number=page_number,
                        metadata=metadata,
                    )
                )
                chunk_counter += 1
                _reset_pending()

            for info in block_infos:
                has_body = bool(info["body_lines"])
                has_footnote = bool(info["footnote_lines"])

                if has_body:
                    if not pending_lines:
                        pending_lines = list(info["body_lines"])
                        pending_blocks = [info["block_index"]]
                        pending_bbox = [info["x0"], info["y0"], info["x1"], info["y1"]]
                        current_span = {
                            "x0": info["x0"],
                            "y0": info["y0"],
                            "x1": info["x1"],
                            "y1": info["y1"],
                            "body_lines": list(info["body_lines"]),
                        }
                    else:
                        should_merge = current_span is not None and _should_merge(current_span, info)
                        pending_text_length = sum(len(line) for line in pending_lines)
                        if should_merge or pending_text_length < MIN_PARAGRAPH_LENGTH:
                            pending_lines.extend(info["body_lines"])
                            pending_blocks.append(info["block_index"])
                            pending_bbox[0] = min(pending_bbox[0], info["x0"])
                            pending_bbox[1] = min(pending_bbox[1], info["y0"])
                            pending_bbox[2] = max(pending_bbox[2], info["x1"])
                            pending_bbox[3] = max(pending_bbox[3], info["y1"])
                            current_span = {
                                "x0": min(current_span["x0"], info["x0"]) if current_span else info["x0"],
                                "y0": min(current_span["y0"], info["y0"]) if current_span else info["y0"],
                                "x1": max(current_span["x1"], info["x1"]) if current_span else info["x1"],
                                "y1": max(current_span["y1"], info["y1"]) if current_span else info["y1"],
                                "body_lines": list(pending_lines),
                            }
                        else:
                            _flush_pending()
                            pending_lines = list(info["body_lines"])
                            pending_blocks = [info["block_index"]]
                            pending_bbox = [info["x0"], info["y0"], info["x1"], info["y1"]]
                            current_span = {
                                "x0": info["x0"],
                                "y0": info["y0"],
                                "x1": info["x1"],
                                "y1": info["y1"],
                                "body_lines": list(info["body_lines"]),
                            }
                else:
                    _flush_pending()

                if has_footnote and (info["y0"] / page_height) >= FOOTNOTE_Y_RATIO:
                    footnote_content = " ".join(info["footnote_lines"])
                    char_start, char_end = _allocate_char_span(footnote_content)
                    metadata = _enrich_metadata(
                        info["x0"],
                        info["y0"],
                        info["x1"],
                        info["y1"],
                        page_width=page_width,
                        page_height=page_height,
                        base={
                            "block_index": info["block_index"],
                            "footnote_lines": info["footnote_lines"],
                            "char_start": char_start,
                            "char_end": char_end,
                        },
                    )
                    hash_value = _sentence_hash(footnote_content)
                    if hash_value:
                        metadata["sentence_hash"] = hash_value
                    chunks.append(
                        build_chunk(
                            f"pdf-footnote-{page_number}-{chunk_counter}",
                            chunk_type="footnote",
                            content=footnote_content,
                            section="footnote",
                            source="pdf",
                            page_number=page_number,
                            metadata=metadata,
                        )
                    )
                    chunk_counter += 1

            _flush_pending()

            tables = page.find_tables()
            for table_index, table in enumerate(tables, start=1):
                table_data = table.extract()
                if not table_data:
                    continue

                table_text = _table_to_text(table_data)
                char_start, char_end = _allocate_char_span(table_text)
                cells_metadata: List[Dict[str, Any]] = []
                try:
                    for cell in table.cells or []:
                        cell_bbox = _sanitize_rect(cell.bbox)
                        cells_metadata.append(
                            {
                                "row": getattr(cell, "row", None),
                                "column": getattr(cell, "col", None),
                                "bbox": cell_bbox,
                                "y_start_pct": _clamp_pct(
                                    (cell_bbox[1] / page_height) * 100.0 if page_height else 0.0
                                ),
                                "y_end_pct": _clamp_pct(
                                    (cell_bbox[3] / page_height) * 100.0 if page_height else 0.0
                                ),
                                "span": getattr(cell, "span", None),
                            }
                        )
                except Exception:
                    logger.debug("Failed to read cell metadata for table on page %s.", page_number, exc_info=True)

                table_bbox = _sanitize_rect(table.bbox)
                table_metadata = _enrich_metadata(
                    table_bbox[0],
                    table_bbox[1],
                    table_bbox[2],
                    table_bbox[3],
                    page_width=page_width,
                    page_height=page_height,
                    base={
                        "table_json": table_data,
                        "cell_coordinates": cells_metadata,
                        "table_index": table_index,
                        "char_start": char_start,
                        "char_end": char_end,
                    },
                )
                hash_value = _sentence_hash(table_text)
                if hash_value:
                    table_metadata["sentence_hash"] = hash_value

                chunks.append(
                    build_chunk(
                        f"pdf-table-{page_number}-{chunk_counter}",
                        chunk_type="table",
                        content=table_text,
                        section="table",
                        source="pdf",
                        page_number=page_number,
                        metadata=table_metadata,
                    )
                )
                chunk_counter += 1

            dict_blocks = page.get_text("dict").get("blocks", [])
            for block in dict_blocks:
                if block.get("type") != 1:
                    continue
                bbox = block.get("bbox", [0, 0, 0, 0])
                figure_content = f"Figure image on page {page_number}"
                char_start, char_end = _allocate_char_span(figure_content)
                figure_metadata = _enrich_metadata(
                    float(bbox[0]),
                    float(bbox[1]),
                    float(bbox[2]),
                    float(bbox[3]),
                    page_width=page_width,
                    page_height=page_height,
                    base={"image": block.get("image"), "char_start": char_start, "char_end": char_end},
                )
                hash_value = _sentence_hash(figure_content)
                if hash_value:
                    figure_metadata["sentence_hash"] = hash_value
                chunks.append(
                    build_chunk(
                        f"pdf-figure-{page_number}-{chunk_counter}",
                        chunk_type="figure",
                        content=figure_content,
                        section="figure",
                        source="pdf",
                        page_number=page_number,
                        metadata=figure_metadata,
                    )
                )
                chunk_counter += 1

        logger.info("Extracted %d chunks from '%s'.", len(chunks), pdf_path)
        return chunks

    except Exception as exc:
        logger.error("Error while parsing PDF '%s': %s", pdf_path, exc, exc_info=True)
        raise
