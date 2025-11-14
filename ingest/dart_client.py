"""Client for interacting with the DART OpenAPI."""

from __future__ import annotations

import io
import json
import logging
import os
import time
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import xmltodict
from dotenv import load_dotenv

from services.ingest_errors import FatalIngestError, TransientIngestError

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DART_API_BASE = "https://opendart.fss.or.kr/api"
CORP_CODE_URL = f"{DART_API_BASE}/corpCode.xml"
DOCUMENT_URL = f"{DART_API_BASE}/document.xml"


def _load_json_payload(text: str, *, context: str) -> Dict[str, Any]:
    stripped = (text or "").strip()
    if not stripped:
        logger.warning("Empty JSON payload received from %s.", context)
        raise FatalIngestError(f"{context} returned an empty body.")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as exc:
        preview = stripped[:160]
        logger.error("Unable to decode JSON payload from %s: %s (body preview=%s)", context, exc, preview)
        raise FatalIngestError(f"{context} responded with invalid JSON.") from exc


DS005_ENDPOINTS: Dict[str, str] = {
    # Representative subset of DS005 endpoints. Extend as needed.
    "capital_increase_mixed": "pifricDecsn.json",  # 유무상증자 결정
    "merger": "cmpMgDecsn.json",  # 회사합병 결정
    "business_suspension": "bsnSp.json",  # 영업정지
    "treasury_stock_acquisition": "tsstkAqDecsn.json",  # 자기주식 취득 결정
}


class DartClient:
    """Wrapper around DART OpenAPI endpoints used in M1 pipeline."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or os.getenv("DART_API_KEY")
        if not self.api_key:
            raise ValueError("DART_API_KEY is missing in environment variables.")
        self._corp_codes: Optional[Dict[str, str]] = None

    def _load_corp_codes(self) -> Dict[str, str]:
        """Fetch and cache the DART corporation code table."""
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.get(CORP_CODE_URL, params={"crtfc_key": self.api_key})
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Failed to download corp code ZIP: %s", exc)
            raise TransientIngestError("Failed to download corp code ZIP.") from exc

        content_type = response.headers.get("Content-Type", "")
        if "zip" not in content_type.lower():
            logger.warning("Unexpected corp code content type: %s", content_type)

        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                xml_bytes = zip_file.read("CORPCODE.xml")
        except zipfile.BadZipFile as exc:
            raise FatalIngestError("Downloaded corp code archive is corrupted.") from exc

        parsed = xmltodict.parse(xml_bytes)
        corp_list = parsed.get("result", {}).get("list", [])
        codes = {item["corp_code"]: item["corp_name"] for item in corp_list}
        logger.info("Loaded %d corp codes from DART.", len(codes))
        return codes

    @property
    def corp_codes(self) -> Dict[str, str]:
        if self._corp_codes is None:
            self._corp_codes = self._load_corp_codes()
        return self._corp_codes

    def find_corp_code(self, name: str) -> Optional[str]:
        """Return a corporation code whose name contains the given string."""
        name_lower = name.lower()
        for code, corp_name in self.corp_codes.items():
            if name_lower in corp_name.lower():
                return code
        return None

    def list_recent_filings(
        self,
        since: datetime,
        until: Optional[datetime] = None,
        page_no: int = 1,
        page_count: int = 100,
        max_pages: Optional[int] = None,
        throttle_seconds: float = 0.2,
        corp_code: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Return filings submitted between ``since`` and ``until`` (inclusive).

        Fetches pages sequentially until the API stops returning results or ``max_pages`` is
        reached. A small delay is applied between requests to respect OpenDART rate limits.
        """
        aggregated: List[Dict[str, str]] = []
        current_page = page_no
        fetched_pages = 0
        range_end_dt = until or datetime.now()
        end_date = range_end_dt.strftime("%Y%m%d")
        range_end_display = range_end_dt.date()

        try:
            with httpx.Client(timeout=60.0) as client:
                while True:
                    params = {
                        "crtfc_key": self.api_key,
                        "bgn_de": since.strftime("%Y%m%d"),
                        "end_de": end_date,
                        "page_no": current_page,
                        "page_count": page_count,
                    }
                    if corp_code:
                        params["corp_code"] = corp_code
                    try:
                        response = client.get(f"{DART_API_BASE}/list.json", params=params)
                        response.raise_for_status()
                    except httpx.HTTPError as exc:
                        logger.error("Failed to list recent filings: %s", exc)
                        raise TransientIngestError("DART list.json call failed.") from exc

                    try:
                        text = response.content.decode("utf-8")
                    except UnicodeDecodeError:
                        text = response.content.decode("euc-kr", errors="replace")
                    payload = _load_json_payload(text, context="list.json")
                    if payload.get("status") != "000":
                        message = payload.get("message", "Unknown DART error")
                        logger.error("DART returned error status (page %s): %s", current_page, message)
                        raise RuntimeError(f"DART error: {message}")

                    page_items = payload.get("list") or []
                    aggregated.extend(page_items)
                    fetched_pages += 1
                    logger.info(
                        "Fetched %d filings from page %d (total=%d) between %s and %s.",
                        len(page_items),
                        current_page,
                        len(aggregated),
                        since.date(),
                        range_end_display,
                    )

                    if max_pages is not None and fetched_pages >= max_pages:
                        break
                    if len(page_items) < page_count or not page_items:
                        break

                    current_page += 1
                    if throttle_seconds > 0:
                        time.sleep(throttle_seconds)
        except TransientIngestError:
            raise
        except FatalIngestError:
            raise
        except Exception as exc:
            raise FatalIngestError("Unexpected error while listing recent filings.") from exc

        return aggregated

    def download_document_zip(self, receipt_no: str) -> Optional[bytes]:
        """Download the raw filing ZIP payload for a given receipt number."""
        params = {"crtfc_key": self.api_key, "rcept_no": receipt_no}
        try:
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                response = client.get(DOCUMENT_URL, params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Failed to download document for %s: %s", receipt_no, exc)
            raise TransientIngestError(f"Document download failed for {receipt_no}.") from exc

        content_type = response.headers.get("Content-Type", "").lower()
        content_bytes = response.content

        if (
            "zip" in content_type
            or content_bytes.startswith(b"PK")
            or zipfile.is_zipfile(io.BytesIO(content_bytes))
        ):
            return content_bytes

        if content_bytes.startswith(b"%PDF"):
            return content_bytes

        stripped = content_bytes.lstrip()
        lowered_prefix = stripped[:32].lower()
        if lowered_prefix.startswith(b"<html") or lowered_prefix.startswith(b"<!doctype html"):
            logger.warning(
                "DART document download returned viewer HTML for %s; falling back to viewer scraping.",
                receipt_no,
            )
            return None
        if stripped.startswith(b"<?xml") or stripped.startswith(b"<"):
            try:
                payload = xmltodict.parse(content_bytes)
            except Exception:
                return content_bytes

            status = payload.get("result", {}).get("status")
            if status and status != "000":
                message = payload.get("result", {}).get("message", "Unknown error")
                logger.warning(
                    "DART document download returned error XML (%s): %s", receipt_no, message
                )
                return None
            return content_bytes

        logger.warning(
            "DART document download returned unsupported payload (%s): content-type=%s", receipt_no, content_type
        )
        return None

    @staticmethod
    def make_viewer_url(receipt_no: str) -> str:
        return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}"

    @staticmethod
    def make_document_url(receipt_no: str) -> str:
        return f"{DOCUMENT_URL}?rcept_no={receipt_no}"

    def _get_json(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch JSON payload from a DART endpoint with shared error handling."""
        payload: Dict[str, Any] = {}
        merged_params = {"crtfc_key": self.api_key, **params}
        url = f"{DART_API_BASE}/{endpoint}"
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.get(url, params=merged_params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("DART request failed for %s: %s", endpoint, exc)
            raise TransientIngestError(f"DART endpoint {endpoint} call failed.") from exc

        try:
            text = response.content.decode("utf-8")
        except UnicodeDecodeError:
            text = response.content.decode("euc-kr", errors="replace")

        payload = _load_json_payload(text, context=endpoint)

        status = payload.get("status")
        if status and status != "000":
            message = payload.get("message", "Unknown DART error")
            logger.warning("DART endpoint %s returned status %s: %s", endpoint, status, message)
        return payload

    def fetch_single_account_summary(self, corp_code: str, bsns_year: int, reprt_code: str) -> Dict[str, Any]:
        """Fetch DE002 (단일회사 주요계정) summary."""
        return self._get_json(
            "fnlttSinglAcnt.json",
            {"corp_code": corp_code, "bsns_year": str(bsns_year), "reprt_code": reprt_code},
        )

    def fetch_single_account_detail(
        self,
        corp_code: str,
        bsns_year: int,
        reprt_code: str,
        fs_div: str = "CFS",  # or "OFS"
    ) -> Dict[str, Any]:
        """Fetch DE003 (단일회사 전표준재무제표) data."""
        return self._get_json(
            "fnlttSinglAcntAll.json",
            {
                "corp_code": corp_code,
                "bsns_year": str(bsns_year),
                "reprt_code": reprt_code,
                "fs_div": fs_div,
            },
        )


    def fetch_major_shareholders(self, corp_code: str, bsns_year: int, reprt_code: str) -> Dict[str, Any]:
        """Fetch DE004 (임원·주요주주 현황) dataset."""
        return self._get_json(
            "majorstock.json",
            {"corp_code": corp_code, "bsns_year": str(bsns_year), "reprt_code": reprt_code},
        )

    def fetch_major_issues_for_filing(
        self,
        corp_code: str,
        receipt_no: Optional[str],
        receipt_date: Optional[datetime],
        endpoint_keys: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch DS005 (주요사항 보고) entries associated with a specific filing.

        OpenDART exposes DS005 data via multiple issue-specific endpoints rather than a single
        majorissue.json feed. We therefore query a curated subset of endpoints and return the rows
        whose rcept_no matches the filing's receipt number.
        """
        if not receipt_no:
            logger.debug("Skipping DS005 lookup because receipt_no is missing.")
            return []

        target_date = receipt_date or datetime.utcnow()
        query_date = target_date.strftime("%Y%m%d")
        selected_endpoints = endpoint_keys or list(DS005_ENDPOINTS.keys())
        issues: List[Dict[str, Any]] = []

        for key in selected_endpoints:
            endpoint = DS005_ENDPOINTS.get(key)
            if not endpoint:
                logger.warning("Unknown DS005 endpoint key '%s'; skipping.", key)
                continue

            payload = self._get_json(
                endpoint,
                {
                    "corp_code": corp_code,
                    "bgn_de": query_date,
                    "end_de": query_date,
                },
            )

            status = str(payload.get("status", ""))
            message = payload.get("message")

            if status == "000":
                for row in payload.get("list") or []:
                    if row.get("rcept_no") == receipt_no:
                        row["_issue_type"] = key
                        row["_endpoint"] = endpoint
                        issues.append(row)
            elif status == "013":
                logger.debug(
                    "No DS005 records for corp=%s date=%s via %s",
                    corp_code,
                    query_date,
                    endpoint,
                )
                continue
            else:
                logger.warning(
                    "DS005 endpoint %s returned status %s: %s",
                    endpoint,
                    status,
                    message,
                )

        return issues


__all__ = ["DartClient"]
