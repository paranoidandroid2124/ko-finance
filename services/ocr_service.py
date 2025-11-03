"""OCR helpers backed by Google Cloud Vision."""

from __future__ import annotations

from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

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


def is_enabled() -> bool:
    """Return True if OCR is allowed and the Vision client is importable."""
    return _OCR_ENABLED and vision is not None


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
    scale = max(_VISION_RENDER_DPI / 72.0, 1.0)
    page_limit = min(max_pages or _VISION_MAX_PAGES, len(document))

    chunks: List[Dict[str, Any]] = []
    for index in range(page_limit):
        page_number = index + 1
        page = document[index]
        try:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            image_bytes = pixmap.tobytes("png")
        except Exception as exc:
            logger.warning(
                "Vision OCR skipped; failed to rasterise page %d for '%s': %s",
                page_number,
                pdf_path,
                exc,
            )
            continue

        try:
            response = client.document_text_detection(
                image=vision.Image(content=image_bytes),
                image_context={"language_hints": hints} if hints else None,
            )
        except Exception as exc:
            logger.warning(
                "Vision OCR request failed for '%s' page %d: %s",
                pdf_path,
                page_number,
                exc,
            )
            continue

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

        text = normalize_text(annotation.text)
        if not text:
            continue

        metadata: Dict[str, Any] = {
            "engine": "gcp_vision",
            "language_hints": hints,
            "mode": "document_text_detection",
        }
        avg_conf = _average_confidence(annotation)
        if avg_conf is not None:
            metadata["avg_confidence"] = round(avg_conf, 4)

        chunks.append(
            build_chunk(
                f"ocr-text-{page_number}",
                chunk_type="text",
                content=text,
                section="ocr",
                source="ocr",
                page_number=page_number,
                metadata=metadata,
            )
        )

    document.close()
    if chunks:
        logger.info(
            "Vision OCR extracted %d text chunks from '%s' (pages=%d).",
            len(chunks),
            pdf_path,
            page_limit,
        )
    return chunks


__all__ = ["extract_text_chunks_from_pdf", "is_enabled"]
