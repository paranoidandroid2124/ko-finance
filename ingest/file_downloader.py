"""Utilities for downloading and unpacking DART filing documents."""

from __future__ import annotations

import io
import logging
import os
import re
import time
import zipfile
from html import unescape
from pathlib import Path
from typing import List, Optional, Tuple, TypedDict
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from lxml import etree, html as lxml_html

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_RETRIES = 3
RETRY_DELAY_SEC = 1.5

RECOVER_HTML_PARSER = etree.HTMLParser(recover=True)
PDF_FUNCTION_CALL_RE = re.compile(
    r"(?:openPdfDownload|showPdf|pdfDownload|downPdf)\s*\(\s*['\"]?(?P<rcp>\d+)['\"]?\s*,\s*['\"]?(?P<dcm>\d+)['\"]?",
    re.IGNORECASE,
)
DCM_ONLY_RE = re.compile(r"dcm[_]?no[^0-9]{0,8}(?P<dcm>\d{5,})", re.IGNORECASE)
RECEIPT_NUMBER_RE = re.compile(r"rcp(?:No|_?no|t[_]?no)[^\d]{0,4}(?P<rcp>\d{5,})", re.IGNORECASE)
FILE_URL_RE = re.compile(r"https?://[^\s\"'>')\]]+?(?:pdf|zip)[^\s\"'>')\]]*", re.IGNORECASE)
RECEIPT_QUERY_KEYS = ("rcpNo", "rcp_no", "rcpno", "rceptNo", "rcept_no")
DOC_QUERY_KEYS = ("dcmNo", "dcm_no", "dcmno")
FILENAME_QUERY_KEYS = ("fl_nm", "filename")


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
            normalized_url = _force_https(url)
            response = client.get(normalized_url)
            response.raise_for_status()
            return response
        except (httpx.HTTPError, httpx.RemoteProtocolError) as exc:
            last_error = exc
            logger.warning("Request to %s failed (%d/%d): %s", normalized_url, attempt, MAX_RETRIES, exc)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_SEC)
    assert last_error is not None
    raise last_error


class AttachmentInfo(TypedDict):
    name: str
    path: str
    type: str


class FilingPackage(TypedDict, total=False):
    rcp_no: str
    download_url: Optional[str]
    pdf: Optional[str]
    xml: List[str]
    attachments: List[AttachmentInfo]


def parse_filing_bundle(
    receipt_no: str,
    data: bytes,
    save_dir: str,
    download_url: Optional[str] = None,
    content_type_header: Optional[str] = None,
) -> Optional[FilingPackage]:
    """Persist downloaded ZIP/PDF content and return file metadata."""
    base_dir = Path(save_dir) / receipt_no
    base_dir.mkdir(parents=True, exist_ok=True)

    package: FilingPackage = {
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
        lowered_prefix = stripped[:32].lower()
        if lowered_prefix.startswith(b"<html") or lowered_prefix.startswith(b"<!doctype html"):
            logger.warning(
                "Viewer HTML detected for receipt %s while parsing bundle; requesting fallback.",
                receipt_no,
            )
            return None
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


def _force_https(url: str) -> str:
    sanitized = url.strip()
    if sanitized.startswith("http://"):
        return "https://" + sanitized[len("http://") :]
    return sanitized


def _recover_html_dom(markup: str) -> Optional[lxml_html.HtmlElement]:
    if not markup:
        return None
    try:
        return lxml_html.fromstring(markup, parser=RECOVER_HTML_PARSER)
    except (etree.ParserError, ValueError, TypeError):
        return None


def _extract_numeric_param(query: dict[str, List[str]], keys: Tuple[str, ...]) -> Optional[str]:
    for key in keys:
        values = query.get(key)
        if not values:
            continue
        for value in values:
            digits = re.search(r"(\d{5,})", value)
            if digits:
                return digits.group(1)
    return None


def _extract_receipt_no(viewer_url: str, html_text: str) -> Optional[str]:
    parsed = urlparse(viewer_url)
    query = parse_qs(parsed.query)
    receipt = _extract_numeric_param(query, RECEIPT_QUERY_KEYS)
    if receipt:
        return receipt
    if html_text:
        match = RECEIPT_NUMBER_RE.search(html_text)
        if match:
            return match.group("rcp")
    return None


def _extract_receipt_no_from_urls(urls: List[str]) -> Optional[str]:
    for url in urls:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        receipt = _extract_numeric_param(query, RECEIPT_QUERY_KEYS)
        if receipt:
            return receipt
    return None


def _extract_params_from_urls(urls: List[str], receipt_hint: Optional[str]) -> Optional[Tuple[str, str]]:
    for url in urls:
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        receipt = _extract_numeric_param(query, RECEIPT_QUERY_KEYS) or receipt_hint
        doc = _extract_numeric_param(query, DOC_QUERY_KEYS)
        if receipt and doc:
            return receipt, doc
    return None


def _extract_download_params(
    html_text: str,
    dom: Optional[lxml_html.HtmlElement],
    receipt_hint: Optional[str],
    candidate_urls: List[str],
) -> Optional[Tuple[str, str]]:
    if html_text:
        match = PDF_FUNCTION_CALL_RE.search(html_text)
        if match:
            receipt = match.group("rcp") or receipt_hint
            doc = match.group("dcm")
            if receipt and doc:
                return receipt, doc

    if dom is not None:
        for attr in dom.xpath("//*[@onclick]/@onclick"):
            match = PDF_FUNCTION_CALL_RE.search(attr)
            if match:
                receipt = match.group("rcp") or receipt_hint
                doc = match.group("dcm")
                if receipt and doc:
                    return receipt, doc
        if receipt_hint:
            for value in dom.xpath("//*[@data-dcm-no]/@data-dcm-no"):
                digits = re.search(r"(\d{5,})", value)
                if digits:
                    return receipt_hint, digits.group(1)

    params = _extract_params_from_urls(candidate_urls, receipt_hint)
    if params:
        return params

    if receipt_hint and html_text:
        dcm_match = DCM_ONLY_RE.search(html_text)
        if dcm_match:
            return receipt_hint, dcm_match.group("dcm")

    return None


def _extract_candidate_file_urls(html_text: str) -> List[str]:
    if not html_text:
        return []

    urls: List[str] = []
    seen: set[str] = set()
    for match in FILE_URL_RE.finditer(html_text):
        raw = match.group(0)
        cleaned = unescape(raw).rstrip(")'\"")
        cleaned = _force_https(cleaned.rstrip("]"))
        parsed = urlparse(cleaned)
        if not parsed.netloc:
            continue
        if not parsed.netloc.endswith("fss.or.kr"):
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        urls.append(cleaned)
    return urls


def _derive_filename_from_url(url: str, receipt_no: str, index: int, detected_type: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in FILENAME_QUERY_KEYS:
        values = query.get(key)
        if values and values[0]:
            return unquote(values[0])
    if parsed.path:
        basename = os.path.basename(parsed.path)
        if basename:
            return basename
    suffix = ".zip" if detected_type.startswith("application/zip") else ".pdf"
    return f"{receipt_no}_{index}{suffix}"


def _download_from_candidate_urls(
    client: httpx.Client,
    urls: List[str],
    receipt_no: str,
    save_dir: str,
) -> Optional[FilingPackage]:
    if not urls:
        return None

    package: Optional[FilingPackage] = None
    base_dir = Path(save_dir) / receipt_no
    base_dir.mkdir(parents=True, exist_ok=True)

    def ensure_package() -> FilingPackage:
        nonlocal package
        if package is None:
            package = {
                "rcp_no": receipt_no,
                "download_url": None,
                "pdf": None,
                "xml": [],
                "attachments": [],
            }
        return package

    for idx, url in enumerate(urls):
        try:
            response = _get_with_retry(client, _force_https(url))
        except Exception as exc:
            logger.debug("Candidate asset fetch failed for %s: %s", url, exc)
            continue

        data = response.content
        content_type = response.headers.get("content-type")
        detected_type = _guess_content_type(data, content_type)

        if detected_type.startswith("application/zip"):
            parsed = parse_filing_bundle(
                receipt_no=receipt_no,
                data=data,
                save_dir=save_dir,
                download_url=url,
                content_type_header=content_type,
            )
            if parsed:
                logger.info("Recovered filing bundle via direct ZIP link %s.", url)
                return parsed
            continue

        if not detected_type.endswith("pdf"):
            continue

        pkg = ensure_package()
        filename = _derive_filename_from_url(url, receipt_no, idx, detected_type)
        output_path = base_dir / filename
        output_path.write_bytes(data)
        attachment_type = output_path.suffix.lower().lstrip(".") or "pdf"
        pkg["pdf"] = pkg.get("pdf") or str(output_path.resolve())
        pkg["attachments"].append(
            {"name": filename, "path": str(output_path.resolve()), "type": attachment_type}
        )

    return package


def fetch_viewer_bundle(viewer_url: str, save_dir: str) -> Optional[FilingPackage]:
    """Download a filing bundle by scraping the DART viewer page."""
    viewer_url = _force_https(viewer_url)
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as client:
            response = _get_with_retry(client, viewer_url)
            viewer_html = response.text
            dom = _recover_html_dom(viewer_html)
            candidate_urls = _extract_candidate_file_urls(viewer_html)
            receipt_hint = _extract_receipt_no(viewer_url, viewer_html) or _extract_receipt_no_from_urls(candidate_urls)

            download_params = _extract_download_params(viewer_html, dom, receipt_hint, candidate_urls)
            if not download_params:
                logger.warning("Structured download hooks missing for viewer %s; trying regex fallback.", viewer_url)
                fallback_receipt = receipt_hint or "unknown"
                fallback_package = _download_from_candidate_urls(client, candidate_urls, fallback_receipt, save_dir)
                if fallback_package:
                    return fallback_package
                logger.error("Unable to locate PDF download information on viewer page: %s", viewer_url)
                return None

            receipt_no, doc_no = download_params
            download_page_url = f"https://dart.fss.or.kr/pdf/download/main.do?rcp_no={receipt_no}&dcm_no={doc_no}"
            download_page = _get_with_retry(client, download_page_url)
            download_soup = BeautifulSoup(download_page.text, "lxml")

            package: Optional[FilingPackage] = None
            base_dir = Path(save_dir) / receipt_no
            base_dir.mkdir(parents=True, exist_ok=True)

            def ensure_package() -> FilingPackage:
                nonlocal package
                if package is None:
                    package = {
                        "rcp_no": receipt_no,
                        "download_url": download_page_url,
                        "pdf": None,
                        "xml": [],
                        "attachments": [],
                    }
                return package

            for btn in download_soup.select("a.btnFile"):
                href = btn.get("href")
                if not href:
                    continue
                full_url = urljoin("https://dart.fss.or.kr", href)
                file_response = _get_with_retry(client, _force_https(full_url))
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
                    filename = f"{receipt_no}_{len(pkg['attachments'])}.dat"

                output_path = base_dir / filename
                output_path.write_bytes(data)
                attachment_type = output_path.suffix.lower().lstrip(".") or "file"
                if attachment_type == "pdf":
                    if pkg.get("pdf") is None:
                        pkg["pdf"] = str(output_path.resolve())
                elif attachment_type in {"xml", "xbrl"}:
                    pkg["xml"].append(str(output_path.resolve()))

                pkg["attachments"].append(
                    {"name": filename, "path": str(output_path.resolve()), "type": attachment_type}
                )

            if package:
                return package

            fallback_urls = _extract_candidate_file_urls(download_page.text)
            fallback_package = _download_from_candidate_urls(client, fallback_urls, receipt_no, save_dir)
            if fallback_package:
                return fallback_package

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
    pdf_path = package.get("pdf")
    return pdf_path


__all__ = ["parse_filing_bundle", "fetch_viewer_bundle", "download_dart_pdf"]
