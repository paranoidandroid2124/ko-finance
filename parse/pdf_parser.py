"""Extract structured content from PDF filings."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import fitz  # PyMuPDF

from parse.chunk_utils import build_chunk, normalize_text

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MIN_PARAGRAPH_LENGTH = 50
FOOTNOTE_PATTERN = re.compile(r"^(\(?\d+[\)\.]|\[\d+\]|[*†‡])\s+", re.IGNORECASE)
FOOTNOTE_Y_RATIO = 0.8


def _sanitize_rect(rect: Any) -> List[float]:
    if hasattr(rect, "x0") and hasattr(rect, "y0") and hasattr(rect, "x1") and hasattr(rect, "y1"):
        return [float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)]
    if isinstance(rect, (list, tuple)) and len(rect) >= 4:
        return [float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])]
    return [0.0, 0.0, 0.0, 0.0]


def _table_to_text(table_data: List[List[str]]) -> str:
    lines: List[str] = []
    for row in table_data:
        sanitized = [normalize_text(cell) if isinstance(cell, str) else "" for cell in row]
        if any(sanitized):
            lines.append(" \t ".join(sanitized))
    return "\n".join(lines)


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

            for block in page.get_text("blocks"):
                x0, y0, x1, y1, raw_text = block[:5]
                block_text = raw_text.strip()
                if not block_text:
                    continue

                lines = [normalize_text(line) for line in block_text.splitlines() if line.strip()]
                footnote_lines = [line for line in lines if FOOTNOTE_PATTERN.match(line)]
                body_lines = [line for line in lines if line not in footnote_lines]

                metadata = {
                    "bbox": [float(x0), float(y0), float(x1), float(y1)],
                    "block_index": block[5] if len(block) > 5 else None,
                }

                if body_lines and sum(len(line) for line in body_lines) >= MIN_PARAGRAPH_LENGTH:
                    chunks.append(
                        build_chunk(
                            f"pdf-text-{page_number}-{chunk_counter}",
                            chunk_type="text",
                            content=" ".join(body_lines),
                            section="body",
                            source="pdf",
                            page_number=page_number,
                            metadata=metadata,
                        )
                    )
                    chunk_counter += 1

                if footnote_lines and (y0 / page_height) >= FOOTNOTE_Y_RATIO:
                    chunks.append(
                        build_chunk(
                            f"pdf-footnote-{page_number}-{chunk_counter}",
                            chunk_type="footnote",
                            content=" ".join(footnote_lines),
                            section="footnote",
                            source="pdf",
                            page_number=page_number,
                            metadata={**metadata, "footnote_lines": footnote_lines},
                        )
                    )
                    chunk_counter += 1

            tables = page.find_tables()
            for table_index, table in enumerate(tables, start=1):
                table_data = table.extract()
                if not table_data:
                    continue

                table_text = _table_to_text(table_data)
                cells_metadata: List[Dict[str, Any]] = []
                try:
                    for cell in table.cells or []:
                        cells_metadata.append(
                            {
                                "row": getattr(cell, "row", None),
                                "column": getattr(cell, "col", None),
                                "bbox": _sanitize_rect(cell.bbox),
                                "span": getattr(cell, "span", None),
                            }
                        )
                except Exception:
                    logger.debug("Failed to read cell metadata for table on page %s.", page_number, exc_info=True)

                chunks.append(
                    build_chunk(
                        f"pdf-table-{page_number}-{chunk_counter}",
                        chunk_type="table",
                        content=table_text,
                        section="table",
                        source="pdf",
                        page_number=page_number,
                        metadata={
                            "bbox": _sanitize_rect(table.bbox),
                            "table_json": table_data,
                            "cell_coordinates": cells_metadata,
                            "table_index": table_index,
                        },
                    )
                )
                chunk_counter += 1

            dict_blocks = page.get_text("dict").get("blocks", [])
            for block in dict_blocks:
                if block.get("type") != 1:
                    continue
                bbox = block.get("bbox", [0, 0, 0, 0])
                chunks.append(
                    build_chunk(
                        f"pdf-figure-{page_number}-{chunk_counter}",
                        chunk_type="figure",
                        content=f"Figure image on page {page_number}",
                        section="figure",
                        source="pdf",
                        page_number=page_number,
                        metadata={
                            "bbox": [float(coord) for coord in bbox],
                            "image": block.get("image"),
                        },
                    )
                )
                chunk_counter += 1

        logger.info("Extracted %d chunks from '%s'.", len(chunks), pdf_path)
        return chunks

    except Exception as exc:
        logger.error("Error while parsing PDF '%s': %s", pdf_path, exc, exc_info=True)
        raise

