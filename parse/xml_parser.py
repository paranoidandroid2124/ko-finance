"""Extract structured chunks from XML/XBRL filings."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from bs4 import BeautifulSoup
from bs4.element import Tag

from parse.chunk_utils import build_chunk, normalize_text

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MIN_PARAGRAPH_LENGTH = 30
PARAGRAPH_TAGS = ("p", "para", "paragraph", "div", "section", "item")
TABLE_TAGS = ("table", "TABLE")
FIGURE_TAGS = ("figure", "FIGURE", "img", "image")


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


def extract_chunks_from_xml(xml_paths: List[str]) -> List[Dict[str, object]]:
    """Return text/table/footnote/figure chunks extracted from XML files."""
    chunks: List[Dict[str, object]] = []

    for xml_path in xml_paths:
        path_obj = Path(xml_path)
        if not path_obj.is_file():
            logger.warning("XML file not found: %s", xml_path)
            continue

        try:
            raw_text = path_obj.read_text(encoding="utf-8", errors="ignore")
            soup = BeautifulSoup(raw_text, "xml")
            source_file = str(path_obj.resolve())
            base_id = path_obj.stem

            for table_index, table_tag in enumerate(soup.find_all(TABLE_TAGS), start=1):
                rows: List[List[str]] = []
                for row in table_tag.find_all("tr"):
                    cells = [
                        normalize_text(cell.get_text(" ", strip=True))
                        for cell in row.find_all(["th", "td"])
                    ]
                    if any(cells):
                        rows.append(cells)

                table_text = "\n".join(" \t ".join(r) for r in rows if any(r))
                chunks.append(
                    build_chunk(
                        f"{base_id}-table-{table_index}",
                        chunk_type="table",
                        content=table_text,
                        section=table_tag.name.lower(),
                        source="xml",
                        metadata=_build_metadata(
                            table_tag,
                            source_file,
                            extra={"table_rows": rows},
                        ),
                    )
                )
                table_tag.extract()

            footnote_tags = soup.find_all(
                lambda tag: bool(tag.name)
                and ("footnote" in tag.name.lower()
                     or "footnote" in " ".join(tag.get("class", [])).lower())
            )
            for footnote_index, footnote_tag in enumerate(footnote_tags, start=1):
                text = normalize_text(footnote_tag.get_text(" ", strip=True))
                if text:
                    chunks.append(
                    build_chunk(
                        f"{base_id}-footnote-{footnote_index}",
                        chunk_type="footnote",
                        content=text,
                        section=footnote_tag.name.lower(),
                        source="xml",
                        metadata=_build_metadata(footnote_tag, source_file),
                    )
                )
                footnote_tag.extract()

            figure_tags = soup.find_all(FIGURE_TAGS)
            for figure_index, figure_tag in enumerate(figure_tags, start=1):
                caption = normalize_text(figure_tag.get_text(" ", strip=True))
                if figure_tag.name.lower() in ("img", "image"):
                    caption = caption or f"Image source: {figure_tag.get('src', '')}"
                if not caption:
                    caption = "Figure extracted from XML"
                chunks.append(
                    build_chunk(
                        f"{base_id}-figure-{figure_index}",
                        chunk_type="figure",
                        content=caption,
                        section=figure_tag.name.lower(),
                        source="xml",
                        metadata=_build_metadata(figure_tag, source_file),
                    )
                )
                figure_tag.extract()

            sequence = 1
            for tag in soup.find_all(PARAGRAPH_TAGS):
                text = normalize_text(tag.get_text(" ", strip=True))
                if len(text) < MIN_PARAGRAPH_LENGTH:
                    continue
                chunks.append(
                    build_chunk(
                        f"{base_id}-text-{sequence}",
                        chunk_type="text",
                        content=text,
                        section=tag.name.lower(),
                        source="xml",
                        metadata=_build_metadata(tag, source_file, include_text=text),
                    )
                )
                sequence += 1

            logger.info("Extracted %d chunks from XML %s.", sequence - 1, xml_path)
        except Exception as exc:
            logger.error("Failed to parse XML %s: %s", xml_path, exc, exc_info=True)

    return chunks


__all__ = ["extract_chunks_from_xml"]


def parse_xml_chunks(xml_paths: List[str]) -> List[Dict[str, object]]:
    """Backward-compatible alias used in legacy tests."""
    return extract_chunks_from_xml(xml_paths)


__all__.append("parse_xml_chunks")
