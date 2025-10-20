"""Utilities for downloading and unpacking DART filing documents."""

from __future__ import annotations

import io
import logging
import re
import time
import zipfile
from pathlib import Path
from typing import Dict, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_RETRIES = 3
RETRY_DELAY_SEC = 1.5


def _guess_content_type(data: bytes, header_value: Optional[str]) -> str:
    if header_value:
        lowered = header_value.lower()
        if lowered:
            return lowered
    if data.startswith(b"PK"):
        return "application/zip"
    if data.startswith(b"%PDF"):
        return "application/pdf"
    return "application/octet-stream"


def _get_with_retry(client: httpx.Client, url: str) -> httpx.Response:
    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = client.get(url)
            response.raise_for_status()
            return response
        except (httpx.HTTPError, httpx.RemoteProtocolError) as exc:
            last_error = exc
            logger.warning("Request to %s failed (%d/%d): %s", url, attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SEC)
    assert last_error is not None
    raise last_error


def parse_filing_bundle(
    receipt_no: str,
    data: bytes,
    save_dir: str,
    download_url: Optional[str] = None,
) -> Optional[Dict[str, object]]:
    """Persist downloaded ZIP/PDF content and return file metadata."""
    base_dir = Path(save_dir) / receipt_no
    base_dir.mkdir(parents=True, exist_ok=True)

    package: Dict[str, object] = {
        "rcp_no": receipt_no,
        "download_url": download_url,
        "pdf": None,
        "xml": [],
        "attachments": [],
    }

    content_type = _guess_content_type(data, None)

    if content_type.startswith("application/zip"):
        logger.info("Extracting ZIP bundle for receipt %s.", receipt_no)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                output_path = base_dir / member.filename
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as source, open(output_path, "wb") as target:
                    target.write(source.read())

                path_str = str(output_path.resolve())
                lower_name = member.filename.lower()
                if lower_name.endswith((".xml", ".xbrl")):
                    package["xml"].append(path_str)
                elif lower_name.endswith(".pdf"):
                    if package["pdf"] is None:
                        package["pdf"] = path_str
                    package["attachments"].append({"name": member.filename, "path": path_str, "type": "pdf"})
                else:
                    package["attachments"].append(
                        {"name": member.filename, "path": path_str, "type": output_path.suffix.lower() or "file"}
                    )

        if not package["xml"]:
            logger.warning("No XML/XBRL files found in ZIP for %s.", receipt_no)

    elif content_type.startswith("application/pdf"):
        pdf_path = base_dir / f"{receipt_no}.pdf"
        pdf_path.write_bytes(data)
        package["pdf"] = str(pdf_path.resolve())
    else:
        logger.error("Unsupported content type %s while parsing receipt %s.", content_type, receipt_no)
        return None

    return package


def fetch_viewer_bundle(viewer_url: str, save_dir: str) -> Optional[Dict[str, object]]:
    """Download a filing bundle by scraping the DART viewer page."""
    try:
        with httpx.Client(timeout=30.0) as client:
            response = _get_with_retry(client, viewer_url)
            soup = BeautifulSoup(response.text, "lxml")

            pattern = r"(?:openPdfDownload|showPdf)\s*\(\s*'([0-9]+)'\s*,\s*'([0-9]+)'"
            match = re.search(pattern, response.text)
            if not match:
                logger.warning("PDF download script not found directly on viewer page: %s", viewer_url)
                link = soup.find("a", onclick=re.compile(pattern))
                if link and isinstance(link.attrs.get("onclick"), str):
                    match = re.search(pattern, link["onclick"])

            if not match:
                logger.error("Unable to locate PDF download information on viewer page: %s", viewer_url)
                return None

            receipt_no, doc_no = match.groups()
            download_url = f"http://dart.fss.or.kr/pdf/download/pdf.do?rcp_no={receipt_no}&dcm_no={doc_no}"
            logger.info("Derived download URL from viewer: %s", download_url)

            file_response = _get_with_retry(client, download_url)
            package = parse_filing_bundle(
                receipt_no=receipt_no,
                data=file_response.content,
                save_dir=save_dir,
                download_url=download_url,
            )
            return package
    except Exception as exc:
        logger.error("Failed to download bundle from viewer %s: %s", viewer_url, exc, exc_info=True)
        return None


def download_dart_pdf(viewer_url: str, save_dir: str) -> Optional[str]:
    """Convenience helper returning only the PDF path."""
    package = fetch_viewer_bundle(viewer_url, save_dir)
    if not package:
        return None
    return package.get("pdf")  # type: ignore[return-value]


__all__ = ["parse_filing_bundle", "fetch_viewer_bundle", "download_dart_pdf"]

