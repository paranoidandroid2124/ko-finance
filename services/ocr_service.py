"""OCR helpers backed by Google Cloud Vision."""

from __future__ import annotations

from collections import Counter
import hashlib
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import fitz  # type: ignore[import]

from core.env import env_bool, env_float, env_int, env_str
from core.logging import get_logger

try:  # pragma: no cover - optional runtime dependency
    from google.cloud import vision
except ImportError:  # pragma: no cover - best-effort fallback
    vision = None  # type: ignore

from parse.chunk_utils import build_chunk, normalize_text

logger = get_logger(__name__)

_OCR_ENABLED = env_bool("ENABLE_VISION_OCR", False)
_VISION_MAX_PAGES = env_int("OCR_VISION_MAX_PAGES", 20, minimum=1)
_VISION_RENDER_DPI = env_float("OCR_VISION_RENDER_DPI", 180.0, minimum=72.0)
_LANGUAGE_HINTS_ENV = env_str("OCR_VISION_LANGUAGE_HINTS", "ko,en")
_VISION_LANGUAGE_HINTS = [
    hint.strip() for hint in (_LANGUAGE_HINTS_ENV or "").split(",") if hint.strip()
]
if not _VISION_LANGUAGE_HINTS:
    _VISION_LANGUAGE_HINTS = ["ko", "en"]

_client: Optional["vision.ImageAnnotatorClient"] = None
_TEXT_LAYER_MIN_CHARS = env_int("OCR_TEXT_LAYER_MIN_CHARS", 40, minimum=0)
_MAX_IMAGE_BYTES = env_int("OCR_VISION_MAX_IMAGE_BYTES", 9_500_000, minimum=1_000_000)
_BATCH_SIZE = env_int("OCR_VISION_BATCH_SIZE", 4, minimum=1)
_PARAGRAPH_MIN_CHARS = env_int("OCR_VISION_PARAGRAPH_MIN_CHARS", 200, minimum=40)
_PARAGRAPH_MAX_CHARS = env_int("OCR_VISION_PARAGRAPH_MAX_CHARS", 1200, minimum=200)


def is_enabled() -> bool:
    """Return True if OCR is allowed and the Vision client is importable."""
    return _OCR_ENABLED and vision is not None


def _sentence_hash(text: str) -> Optional[str]:
    normalized = normalize_text(text) if text else ""
    if not normalized:
        return None
    return hashlib.sha1(normalized.encode("utf-8", errors="ignore")).hexdigest()


def _get_client() -> "vision.ImageAnnotatorClient":
    global _client
    if _client is None:
        if vision is None:  # pragma: no cover - guard for static analysis
            raise RuntimeError("google-cloud-vision is not installed.")
        _client = vision.ImageAnnotatorClient()
    return _client


def _average_confidence(annotation: "vision.TextAnnotation") -> Optional[float]:
    confidences: List[float] = []
    for page in getattr(annotation, "pages", []) or []:
        page_conf = getattr(page, "confidence", None)
        if isinstance(page_conf, (float, int)):
            confidences.append(float(page_conf))
        for block in getattr(page, "blocks", []) or []:
            block_conf = getattr(block, "confidence", None)
            if isinstance(block_conf, (float, int)):
                confidences.append(float(block_conf))
    if confidences:
        return float(mean(confidences))
    return None


def _page_has_machine_text(page: "fitz.Page") -> bool:
    if _TEXT_LAYER_MIN_CHARS <= 0:
        return False
    raw_text = (page.get_text("text") or "").strip()
    return len(raw_text) >= _TEXT_LAYER_MIN_CHARS


def _render_page_image(page: "fitz.Page") -> Optional[Tuple[bytes, str, float]]:
    # Try progressive DPI until payload fits Vision limits.
    dpi_candidates = [_VISION_RENDER_DPI, 160.0, 144.0, 120.0, 100.0, 72.0]
    for dpi in dpi_candidates:
        scale = max(dpi / 72.0, 1.0)
        try:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            png_bytes = pixmap.tobytes("png")
        except Exception as exc:  # pragma: no cover - safety net
            logger.warning("Vision OCR skipped; pixmap render failed: %s", exc)
            return None
        if len(png_bytes) <= _MAX_IMAGE_BYTES:
            return png_bytes, "image/png", dpi
        # Fallback to JPEG when PNG is too large
        jpeg_bytes = pixmap.tobytes("jpg", quality=85)
        if len(jpeg_bytes) <= _MAX_IMAGE_BYTES:
            return jpeg_bytes, "image/jpeg", dpi
    return None


def _paragraph_texts(annotation: "vision.TextAnnotation") -> List[str]:
    paragraphs: List[str] = []
    for page in getattr(annotation, "pages", []) or []:
        for block in getattr(page, "blocks", []) or []:
            for para in getattr(block, "paragraphs", []) or []:
                buffer: List[str] = []
                for word in getattr(para, "words", []) or []:
                    symbols = getattr(word, "symbols", []) or []
                    token = "".join(getattr(symbol, "text", "") for symbol in symbols)
                    if token:
                        buffer.append(token)
                    detected_break = getattr(getattr(word, "property", None), "detected_break", None)
                    if detected_break:
                        break_type = getattr(detected_break, "type_", None)
                        if break_type in (1, 3):  # SPACE or EOL_SURE_SPACE
                            buffer.append(" ")
                        if break_type in (3, 5):  # EOL or LINE_BREAK
                            buffer.append("\n")
                text = normalize_text("".join(buffer))
                if text:
                    paragraphs.append(text)
    return paragraphs


def _collect_common_edge_lines(page_paragraphs: Sequence[List[str]], *, head: int = 2, tail: int = 2) -> set:
    counter: Counter = Counter()
    per_page_edges: List[set] = []
    for paragraphs in page_paragraphs:
        lines: List[str] = []
        for paragraph in paragraphs:
            lines.extend([line.strip() for line in paragraph.splitlines() if line.strip()])
        edge_lines = set(lines[:head] + (lines[-tail:] if tail > 0 else []))
        per_page_edges.append(edge_lines)
        for line in edge_lines:
            counter[line] += 1
    threshold = max(2, len(page_paragraphs) // 2)
    return {line for line, count in counter.items() if count >= threshold and line}


def _chunk_paragraphs(paragraphs: List[str]) -> List[str]:
    if not paragraphs:
        return []
    chunks: List[str] = []
    buffer: List[str] = []
    total_len = 0
    for paragraph in paragraphs:
        para_len = len(paragraph)
        if total_len + para_len >= _PARAGRAPH_MAX_CHARS and buffer:
            chunks.append(normalize_text(" ".join(buffer)))
            buffer = []
            total_len = 0
        buffer.append(paragraph)
        total_len += para_len
        if total_len >= _PARAGRAPH_MIN_CHARS:
            chunks.append(normalize_text(" ".join(buffer)))
            buffer = []
            total_len = 0
    if buffer:
        chunks.append(normalize_text(" ".join(buffer)))
    return [chunk for chunk in chunks if chunk]


def _run_vision_batch(
    client: "vision.ImageAnnotatorClient",
    batch: List[Dict[str, Any]],
    hints: Sequence[str],
    pdf_path: str,
) -> List[Dict[str, Any]]:
    requests = []
    for item in batch:
        image_bytes = item.pop("image_bytes", b"")
        requests.append(
            vision.AnnotateImageRequest(
                image=vision.Image(content=image_bytes),
                features=[vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)],
                image_context={"language_hints": hints} if hints else None,
            )
        )
    try:
        responses = client.batch_annotate_images(requests=requests)
    except Exception as exc:
        logger.warning("Vision OCR batch request failed for '%s': %s", pdf_path, exc)
        return []

    batch_entries: List[Dict[str, Any]] = []
    for item, response in zip(batch, responses.responses):
        page_number = item["page_number"]
        if response.error.message:
            logger.warning(
                "Vision OCR returned error for '%s' page %d: %s",
                pdf_path,
                page_number,
                response.error.message,
            )
            continue
        annotation = response.full_text_annotation
        if not annotation or not annotation.text:
            continue
        paragraphs = _paragraph_texts(annotation)
        if not paragraphs:
            paragraphs = [normalize_text(annotation.text)]
        batch_entries.append(
            {
                "page_number": page_number,
                "paragraphs": paragraphs,
                "avg_conf": _average_confidence(annotation),
                "dpi": item["dpi"],
                "mime": item["mime_type"],
                "bytes": item["bytes"],
            }
        )
    return batch_entries


def extract_text_chunks_from_pdf(
    pdf_path: str,
    *,
    max_pages: Optional[int] = None,
    language_hints: Optional[Iterable[str]] = None,
) -> List[Dict[str, Any]]:
    """Extract OCR text chunks from a PDF using Google Cloud Vision."""
    if not is_enabled():
        return []

    assert vision is not None  # for type-checkers
    hints = list(language_hints) if language_hints else list(_VISION_LANGUAGE_HINTS)

    try:
        document = fitz.open(pdf_path)
    except Exception as exc:  # pragma: no cover - best-effort logging
        logger.warning("Vision OCR skipped; unable to open PDF '%s': %s", pdf_path, exc)
        return []

    client = _get_client()
    page_limit = min(max_pages or _VISION_MAX_PAGES, len(document))

    pending_batch: List[Dict[str, Any]] = []
    page_entries: List[Dict[str, Any]] = []

    def flush_batch() -> None:
        nonlocal pending_batch
        if not pending_batch:
            return
        page_entries.extend(_run_vision_batch(client, pending_batch, hints, pdf_path))
        pending_batch = []

    for index in range(page_limit):
        page_number = index + 1
        page = document[index]
        if _page_has_machine_text(page):
            logger.debug("Skipping OCR for page %d of '%s' (text layer detected).", page_number, pdf_path)
            continue
        rendered = _render_page_image(page)
        if not rendered:
            logger.warning(
                "Vision OCR skipped; failed to prepare image for '%s' page %d (size overflow).",
                pdf_path,
                page_number,
            )
            continue
        image_bytes, mime_type, dpi = rendered
        pending_batch.append(
            {
                "page_number": page_number,
                "image_bytes": image_bytes,
                "mime_type": mime_type,
                "dpi": dpi,
                "bytes": len(image_bytes),
            }
        )
        if len(pending_batch) >= _BATCH_SIZE:
            flush_batch()

    flush_batch()
    document.close()
    if not page_entries:
        return []

    edge_lines = (
        _collect_common_edge_lines([entry["paragraphs"] for entry in page_entries]) if len(page_entries) > 1 else set()
    )
    chunks: List[Dict[str, Any]] = []
    for entry in page_entries:
        filtered_paragraphs = [paragraph for paragraph in entry["paragraphs"] if paragraph.strip() not in edge_lines]
        chunk_texts = _chunk_paragraphs(filtered_paragraphs)
        char_cursor = 0
        for idx, content in enumerate(chunk_texts, start=1):
            text = content.strip()
            if not text:
                continue
            length = len(text)
            start = char_cursor
            end = start + length
            char_cursor = end + (1 if length else 0)
            metadata: Dict[str, Any] = {
                "engine": "gcp_vision",
                "language_hints": hints,
                "mode": "document_text_detection",
                "dpi": entry["dpi"],
                "mime_type": entry["mime"],
                "image_bytes": entry["bytes"],
                "chunk_index": idx,
                "char_start": start,
                "char_end": end,
            }
            if entry["avg_conf"] is not None:
                metadata["avg_confidence"] = round(float(entry["avg_conf"]), 4)
            hash_value = _sentence_hash(text)
            if hash_value:
                metadata["sentence_hash"] = hash_value
            chunks.append(
                build_chunk(
                    f"{Path(pdf_path).stem}-ocr-{entry['page_number']}-{idx}",
                    chunk_type="text",
                    content=text,
                    section="ocr",
                    source="ocr",
                    page_number=entry["page_number"],
                    metadata=metadata,
                )
            )

    if chunks:
        logger.info(
            "Vision OCR extracted %d text chunks from '%s' (pages_processed=%d).",
            len(chunks),
            pdf_path,
            len(page_entries),
        )
    return chunks


__all__ = ["extract_text_chunks_from_pdf", "is_enabled"]
