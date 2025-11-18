"""Extract structured chunks from XML/XBRL filings."""

from __future__ import annotations

import logging
import re
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from bs4 import BeautifulSoup
from bs4.element import Tag

from parse.chunk_utils import build_chunk, normalize_text

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MIN_PARAGRAPH_LENGTH = 200
MIN_LIST_LENGTH = 10
PARAGRAPH_TAGS = ("p", "para", "paragraph", "div", "section", "item")
TABLE_TAGS = ("table", "TABLE")
FIGURE_TAGS = ("figure", "FIGURE", "img", "image")
HEAD_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "title")
LIST_TAGS = ("ul", "ol")
FOOTNOTE_HINT = re.compile(r"(?:주석|각주|비고|^주\)|^\*+|footnote)", re.IGNORECASE)
HEADING_PATTERNS = [
    re.compile(r"^제\s*\d+\s*장", re.IGNORECASE),
    re.compile(r"^제\s*\d+\s*절", re.IGNORECASE),
    re.compile(r"^제\s*\d+\s*항", re.IGNORECASE),
    re.compile(r"^(?:ITEM|Item)\s+\d+(\.\d+)?"),
    re.compile(r"^\d+(\.\d+)*\s+\S+"),
]


def _serialize_attrs(tag) -> Dict[str, str]:
    attrs: Dict[str, str] = {}
    for key, value in tag.attrs.items():
        if isinstance(value, (list, tuple)):
            attrs[key] = " ".join(str(v) for v in value)
        else:
            attrs[key] = str(value)
    return attrs


def _compute_xpath(tag: Tag) -> Optional[str]:
    if not tag or not getattr(tag, "name", None):
        return None
    parts: List[str] = []
    current: Optional[Tag] = tag
    while current and getattr(current, "name", None) and current.name != "[document]":
        parent = current.parent
        if not isinstance(parent, Tag):
            index = 1
        else:
            siblings = [
                sibling
                for sibling in parent.find_all(current.name, recursive=False)
                if isinstance(sibling, Tag)
            ]
            try:
                index = siblings.index(current) + 1
            except ValueError:
                index = 1
        parts.append(f"{current.name}[{index}]")
        current = parent if isinstance(parent, Tag) else None
    if not parts:
        return None
    return "/".join(reversed(parts))


def _build_metadata(tag: Tag, source_file: str, extra: Optional[Dict[str, object]] = None, *, include_text: Optional[str] = None) -> Dict[str, object]:
    metadata: Dict[str, object] = {
        "file_path": source_file,
        "tag": tag.name,
        "attributes": _serialize_attrs(tag),
    }
    xpath = _compute_xpath(tag)
    if xpath:
        metadata["xpath"] = xpath
    if include_text is not None:
        metadata["offset_start"] = 0
        metadata["offset_end"] = len(include_text)
    if extra:
        metadata.update(extra)
    return metadata


def _is_heading_text(text: str) -> bool:
    if not text or len(text.strip()) > 200:
        return False
    normalized = text.strip()
    return any(pattern.search(normalized) for pattern in HEADING_PATTERNS)


def _heading_level(text: str) -> int:
    normalized = text.strip()
    for pattern, level in (
        (re.compile(r"^제\s*\d+\s*장", re.IGNORECASE), 1),
        (re.compile(r"^제\s*\d+\s*절", re.IGNORECASE), 2),
        (re.compile(r"^제\s*\d+\s*항", re.IGNORECASE), 3),
    ):
        if pattern.search(normalized):
            return level
    match = re.match(r"^(?:ITEM|Item)\s+(\d+)", normalized)
    if match:
        return 1
    numbered = re.match(r"^(\d+(?:\.\d+)*)", normalized)
    if numbered:
        return min(numbered.group(1).count(".") + 1, 4)
    return 1


class SectionTracker:
    """Track hierarchical section headers for metadata."""

    def __init__(self) -> None:
        self._stack: List[str] = []

    def update(self, title: str) -> None:
        title = title.strip()
        if not title:
            return
        level = _heading_level(title)
        while len(self._stack) >= level:
            self._stack.pop()
        self._stack.append(title)

    def path(self) -> List[str]:
        return list(self._stack)

    def current_title(self) -> Optional[str]:
        return self._stack[-1] if self._stack else None


def _section_metadata(tag: Tag, source_file: str, tracker: SectionTracker, extra: Optional[Dict[str, object]] = None, *, include_text: Optional[str] = None) -> Dict[str, object]:
    payload: Dict[str, object] = {}
    if extra:
        payload.update(extra)
    path = tracker.path()
    if path:
        payload.setdefault("section_path", path)
        payload.setdefault("section_title", path[-1])
    return _build_metadata(tag, source_file, extra=payload, include_text=include_text)


def _gather_list_block(list_tag: Tag) -> Optional[str]:
    items: List[str] = []
    for li in list_tag.find_all("li", recursive=False):
        text = normalize_text(li.get_text(" ", strip=True))
        if text:
            items.append(text)
    if not items:
        return None
    combined = " • ".join(items)
    return combined if len(combined) >= MIN_LIST_LENGTH else None


MAX_FOOTNOTE_LENGTH = 800


def _looks_like_footnote(tag: Tag, text: str) -> bool:
    """Heuristically detect footnote blocks while avoiding full-document matches."""

    if not text:
        return False

    # Footnotes are typically short; exclude massive blocks such as the whole document.
    if len(text) > MAX_FOOTNOTE_LENGTH:
        return False

    name = (tag.name or "").lower()
    if name in {"footnote", "foot-note", "fn"}:
        return True
    if name in {"document", "body", "cover"}:
        return False

    classes_attr = tag.get("class")
    if isinstance(classes_attr, str):
        classes = classes_attr
    elif isinstance(classes_attr, (list, tuple)):
        classes = " ".join(str(entry) for entry in classes_attr)
    else:
        classes = ""
    if "footnote" in classes.lower():
        return True

    usermark_value = tag.get("usermark")
    usermark = str(usermark_value or "").lower()
    if "footnote" in usermark:
        return True

    # Only inspect the beginning of the text for hint keywords to avoid false positives.
    snippet = text[:200]
    if FOOTNOTE_HINT.search(snippet):
        return True

    return False


def _append_chunk(
    chunks: List[Dict[str, object]],
    seen_hashes: set,
    *,
    chunk_id: str,
    chunk_type: str,
    content: str,
    tag: Tag,
    source_file: str,
    tracker: SectionTracker,
    section: Optional[str] = None,
    include_text: bool = False,
    extra_metadata: Optional[Dict[str, object]] = None,
) -> None:
    normalized = content.strip()
    if not normalized:
        return
    digest = hashlib.sha1(f"{chunk_type}:{normalized}".encode("utf-8", errors="ignore")).hexdigest()
    if digest in seen_hashes:
        return
    seen_hashes.add(digest)
    metadata = _section_metadata(tag, source_file, tracker, extra=extra_metadata, include_text=normalized if include_text else None)
    chunks.append(
        build_chunk(
            chunk_id,
            chunk_type=chunk_type,
            content=normalized,
            section=section or (tag.name.lower() if tag.name else chunk_type),
            source="xml",
            metadata=metadata,
        )
    )


def _extract_table_payload(table_tag: Tag) -> Tuple[Optional[str], Dict[str, Any]]:
    rows: List[List[str]] = []
    for row in table_tag.find_all("tr"):
        cells: List[str] = []
        for cell in row.find_all(["th", "td", "te", "tu", "ts", "tf", "tc", "tds"]):
            cell_text = normalize_text(cell.get_text(" ", strip=True))
            cells.append(cell_text)
        if any(cell.strip() for cell in cells):
            rows.append(cells)
    table_text = "\n".join(" \t ".join(r) for r in rows if any(cell.strip() for cell in r))
    if not table_text:
        table_text = normalize_text(table_tag.get_text(" ", strip=True))
    metadata_extra: Dict[str, Any] = {"table_rows": rows}
    return (table_text or None), metadata_extra


def extract_chunks_from_xml(xml_paths: List[str]) -> List[Dict[str, object]]:
    """Return text/table/footnote/figure chunks extracted from XML files."""
    chunks: List[Dict[str, object]] = []

    for xml_path in xml_paths:
        path_obj = Path(xml_path)
        if not path_obj.is_file():
            logger.warning("XML file not found: %s", xml_path)
            continue

        try:
            raw_bytes = path_obj.read_bytes()
            declared_encoding = "utf-8"
            match = re.search(br'encoding=["\']([^"\']+)["\']', raw_bytes[:200])
            if match:
                declared_encoding = match.group(1).decode("ascii", errors="ignore").lower() or declared_encoding
            try:
                raw_text = raw_bytes.decode(declared_encoding, errors="replace")
            except LookupError:
                raw_text = raw_bytes.decode("utf-8", errors="replace")
            soup = BeautifulSoup(raw_text, "xml")
            source_file = str(path_obj.resolve())
            base_id = path_obj.stem
            tracker = SectionTracker()
            seen_hashes: set = set()
            text_buffer: List[str] = []
            buffer_tag: Optional[Tag] = None
            text_counter = 1
            list_counter = 1
            table_counter = 1
            footnote_counter = 1
            figure_counter = 1

            def flush_text_buffer() -> None:
                nonlocal text_buffer, buffer_tag, text_counter
                if not text_buffer or buffer_tag is None:
                    text_buffer = []
                    buffer_tag = None
                    return
                combined = normalize_text(" ".join(text_buffer))
                if combined:
                    _append_chunk(
                        chunks,
                        seen_hashes,
                        chunk_id=f"{base_id}-text-{text_counter}",
                        chunk_type="text",
                        content=combined,
                        tag=buffer_tag,
                        source_file=source_file,
                        tracker=tracker,
                        include_text=True,
                    )
                    text_counter += 1
                text_buffer = []
                buffer_tag = None

            all_tags = list(soup.find_all(True))
            start_count = len(chunks)
            for tag in all_tags:
                if not isinstance(tag, Tag) or not getattr(tag, "name", None):
                    continue
                lname = tag.name.lower()
                if lname in HEAD_TAGS:
                    title = normalize_text(tag.get_text(" ", strip=True))
                    if _is_heading_text(title):
                        tracker.update(title)
                    continue

                if lname in TABLE_TAGS:
                    flush_text_buffer()
                    table_text, metadata_extra = _extract_table_payload(tag)
                    if table_text:
                        _append_chunk(
                            chunks,
                            seen_hashes,
                            chunk_id=f"{base_id}-table-{table_counter}",
                            chunk_type="table",
                            content=table_text,
                            tag=tag,
                            source_file=source_file,
                            tracker=tracker,
                            extra_metadata=metadata_extra,
                        )
                        table_counter += 1
                    tag.decompose()
                    continue

                if lname in LIST_TAGS:
                    flush_text_buffer()
                    block = _gather_list_block(tag)
                    if block:
                        _append_chunk(
                            chunks,
                            seen_hashes,
                            chunk_id=f"{base_id}-list-{list_counter}",
                            chunk_type="list",
                            content=block,
                            tag=tag,
                            source_file=source_file,
                            tracker=tracker,
                            section="list",
                        )
                        list_counter += 1
                    tag.decompose()
                    continue

                text_value = normalize_text(tag.get_text(" ", strip=True))
                if _looks_like_footnote(tag, text_value):
                    flush_text_buffer()
                    if text_value:
                        _append_chunk(
                            chunks,
                            seen_hashes,
                            chunk_id=f"{base_id}-footnote-{footnote_counter}",
                            chunk_type="footnote",
                            content=text_value,
                            tag=tag,
                            source_file=source_file,
                            tracker=tracker,
                        )
                        footnote_counter += 1
                    tag.decompose()
                    continue

                if lname in FIGURE_TAGS:
                    flush_text_buffer()
                    caption = text_value
                    if lname in ("img", "image"):
                        caption = caption or f"Image source: {tag.get('src', '')}"
                    caption = caption or "Figure extracted from XML"
                    _append_chunk(
                        chunks,
                        seen_hashes,
                        chunk_id=f"{base_id}-figure-{figure_counter}",
                        chunk_type="figure",
                        content=caption,
                        tag=tag,
                        source_file=source_file,
                        tracker=tracker,
                    )
                    figure_counter += 1
                    tag.decompose()
                    continue

                if lname in PARAGRAPH_TAGS:
                    if not text_value:
                        continue
                    if buffer_tag is None:
                        buffer_tag = tag
                    text_buffer.append(text_value)
                    if sum(len(segment) for segment in text_buffer) >= MIN_PARAGRAPH_LENGTH:
                        flush_text_buffer()
                    continue

            flush_text_buffer()
            logger.info("Extracted %d chunks from XML %s.", len(chunks) - start_count, xml_path)
        except Exception as exc:
            logger.error("Failed to parse XML %s: %s", xml_path, exc, exc_info=True)

    return chunks


__all__ = ["extract_chunks_from_xml"]


def parse_xml_chunks(xml_paths: List[str]) -> List[Dict[str, object]]:
    """Backward-compatible alias used in legacy tests."""
    return extract_chunks_from_xml(xml_paths)


__all__.append("parse_xml_chunks")
