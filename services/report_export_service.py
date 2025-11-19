"""Utilities to export investment memos as PDF or Word documents."""

from __future__ import annotations

import base64
import io
from typing import Dict, Iterable, List, Optional

import fitz
import markdown
from docx import Document

PDF_PAGE_RECT = fitz.Rect(36, 36, 559, 806)  # letter-ish margins


def _build_html_document(title: str, markdown_body: str, sources: Iterable[Dict[str, str]]) -> str:
    body_html = markdown.markdown(
        markdown_body,
        extensions=[
            "tables",
            "fenced_code",
            "toc",
        ],
    )
    references = ""
    normalized_sources = list(sources)
    if normalized_sources:
        refs = "".join(
            f"<li><a href='{entry.get('url','')}'>{entry.get('title','Source')}</a> "
            f"<em>{entry.get('date','')}</em></li>"
            for entry in normalized_sources
        )
        references = f"<h3>References</h3><ol>{refs}</ol>"
    return f"""
        <html>
            <head>
                <meta charset="utf-8" />
                <style>
                    body {{
                        font-family: 'Helvetica', 'Arial', sans-serif;
                        font-size: 12pt;
                        line-height: 1.6;
                        color: #111827;
                    }}
                    h1, h2, h3 {{
                        color: #0f172a;
                    }}
                    ol {{
                        padding-left: 18px;
                    }}
                    a {{
                        color: #1d4ed8;
                        text-decoration: none;
                    }}
                </style>
            </head>
            <body>
                <h1>{title}</h1>
                {body_html}
                {references}
            </body>
        </html>
    """


def export_pdf(
    *,
    title: str,
    markdown_body: str,
    sources: Iterable[Dict[str, str]],
    chart_image: Optional[str] = None,
) -> bytes:
    """Render Markdown content into a PDF byte stream."""

    html_document = _build_html_document(title, markdown_body, sources)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_htmlbox(PDF_PAGE_RECT, html_document)
    if chart_image:
        try:
            _, _, payload = chart_image.partition(",")
            image_bytes = base64.b64decode(payload or chart_image)
            chart_page = doc.new_page()
            chart_page.insert_image(PDF_PAGE_RECT, stream=image_bytes)
        except Exception:
            pass
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def export_docx(
    *,
    title: str,
    markdown_body: str,
    sources: Iterable[Dict[str, str]],
    chart_image: Optional[str] = None,
) -> bytes:
    """Render Markdown-like content into a .docx byte stream."""

    document = Document()
    document.add_heading(title, level=0)

    if chart_image:
        try:
            _, _, payload = chart_image.partition(",")
            image_bytes = base64.b64decode(payload or chart_image)
            image_stream = io.BytesIO(image_bytes)
            document.add_heading("Performance Chart", level=1)
            document.add_picture(image_stream, width=document.sections[0].page_width - document.sections[0].left_margin - document.sections[0].right_margin)
        except Exception:
            pass

    for line in markdown_body.splitlines():
        stripped = line.strip()
        if not stripped:
            document.add_paragraph("")
            continue
        if stripped.startswith("# "):
            document.add_heading(stripped[2:].strip(), level=1)
        elif stripped.startswith("## "):
            document.add_heading(stripped[3:].strip(), level=2)
        elif stripped.startswith("- "):
            document.add_paragraph(stripped[2:].strip(), style="List Bullet")
        else:
            document.add_paragraph(stripped)

    normalized_sources: List[Dict[str, str]] = list(sources)
    if normalized_sources:
        document.add_page_break()
        document.add_heading("References", level=1)
        for entry in normalized_sources:
            title_text = entry.get("title") or entry.get("url") or "Source"
            paragraph = document.add_paragraph(style="List Number")
            run = paragraph.add_run(f"{title_text} ")
            run.bold = True
            date_str = entry.get("date")
            if date_str:
                paragraph.add_run(f"({date_str}) ")
            url = entry.get("url")
            if url:
                paragraph.add_run(url)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


__all__ = ["export_pdf", "export_docx"]
