"""Utilities for downloading and unpacking DART filing documents."""

from __future__ import annotations

import io
import logging
import os
import re
import time
import zipfile
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_RETRIES = 3
RETRY_DELAY_SEC = 1.5


def _guess_content_type(data: bytes, header_value: Optional[str]) -> str:
    # Sniffing is often more reliable than potentially generic headers
    if data.startswith(b"PK"):
        return "application/zip"
    if data.startswith(b"%PDF"):
        return "application/pdf"

    # If sniffing fails, check the header for clues
    if header_value:
        lowered = header_value.lower()
        if "zip" in lowered:
            return "application/zip"
        if "pdf" in lowered:
            return "application/pdf"
        return lowered  # Return the header as is

    # If no header and sniffing failed, it's unknown
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
    content_type_header: Optional[str] = None,
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

    content_type = _guess_content_type(data, content_type_header)

    # Some responses are labelled generically (e.g. application/octet-stream) but
    # still contain a valid ZIP payload.  We proactively inspect the bytes so we
    # do not discard legitimate filings.
    zip_buffer = io.BytesIO(data)
    is_zip_payload = content_type.startswith("application/zip")
    if not is_zip_payload:
        try:
            is_zip_payload = zipfile.is_zipfile(zip_buffer)
        except zipfile.BadZipFile:
            is_zip_payload = False
        finally:
            zip_buffer.seek(0)

    if is_zip_payload:
        logger.info(
            "Extracting ZIP bundle for receipt %s (detected content-type: %s).",
            receipt_no,
            content_type_header or content_type,
        )
        with zipfile.ZipFile(zip_buffer) as archive:
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
        stripped = data.lstrip()
        if stripped.startswith(b"<?xml") or stripped.startswith(b"<"):
            # Treat raw XML payloads as valid filings (even if the header did not
            # advertise XML explicitly).
            xml_path = base_dir / f"{receipt_no}.xml"
            xml_path.write_bytes(data)
            package["xml"].append(str(xml_path.resolve()))
            return package

        logger.error("Unsupported content type %s while parsing receipt %s.", content_type, receipt_no)
        return None

    return package


def fetch_viewer_bundle(viewer_url: str, save_dir: str) -> Optional[Dict[str, object]]:
    """Download a filing bundle by scraping the DART viewer page."""
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
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
            download_page_url = f"https://dart.fss.or.kr/pdf/download/main.do?rcp_no={receipt_no}&dcm_no={doc_no}"
            download_page = _get_with_retry(client, download_page_url)
            download_soup = BeautifulSoup(download_page.text, "lxml")

            package: Optional[Dict[str, object]] = None
            base_dir = Path(save_dir) / receipt_no
            base_dir.mkdir(parents=True, exist_ok=True)

            def ensure_package() -> Dict[str, object]:
                nonlocal package
                if package is None:
                    package = {
                        "rcp_no": receipt_no,
                        "download_url": download_page_url,
                        "pdf": None,
                        "xml": [],
                        "attachments": [],
                    }
                return package  # type: ignore[return-value]

            for btn in download_soup.select("a.btnFile"):
                href = btn.get("href")
                if not href:
                    continue
                full_url = urljoin("https://dart.fss.or.kr", href)
                file_response = _get_with_retry(client, full_url)
                content_type = file_response.headers.get("content-type")
                data = file_response.content

                if "zip.do" in href:
                    parsed = parse_filing_bundle(
                        receipt_no=receipt_no,
                        data=data,
                        save_dir=save_dir,
                        download_url=full_url,
                        content_type_header=content_type,
                    )
                    if parsed:
                        package = parsed
                    continue

                pkg = ensure_package()

                parsed_url = urlparse(full_url)
                filename = None
                query = parse_qs(parsed_url.query)
                if "fl_nm" in query:
                    filename = unquote(query["fl_nm"][0])
                elif parsed_url.path:
                    filename = os.path.basename(parsed_url.path)

                if not filename:
                    filename = f"{receipt_no}_{len(pkg['attachments'])}.dat"  # type: ignore[index]

                output_path = base_dir / filename
                output_path.write_bytes(data)
                attachment_type = output_path.suffix.lower().lstrip(".") or "file"
                if attachment_type == "pdf":
                    if pkg.get("pdf") is None:
                        pkg["pdf"] = str(output_path.resolve())
                elif attachment_type in {"xml", "xbrl"}:
                    xml_list = pkg.setdefault("xml", [])  # type: ignore[assignment]
                    if isinstance(xml_list, list):
                        xml_list.append(str(output_path.resolve()))

                attachments = pkg.setdefault("attachments", [])  # type: ignore[assignment]
                if isinstance(attachments, list):
                    attachments.append(
                        {"name": filename, "path": str(output_path.resolve()), "type": attachment_type}
                    )

            if package:
                return package

            logger.error("Download page did not yield any files for %s.", viewer_url)
            return None
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
