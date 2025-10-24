"""Client for interacting with the DART OpenAPI."""

from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import xmltodict
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DART_API_BASE = "https://opendart.fss.or.kr/api"
CORP_CODE_URL = f"{DART_API_BASE}/corpCode.xml"
DOCUMENT_URL = f"{DART_API_BASE}/document.xml"


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
            raise

        content_type = response.headers.get("Content-Type", "")
        if "zip" not in content_type.lower():
            logger.warning("Unexpected corp code content type: %s", content_type)

        with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
            xml_bytes = zip_file.read("CORPCODE.xml")

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
        page_no: int = 1,
        page_count: int = 100,
    ) -> List[Dict[str, str]]:
        """Return filings submitted between ``since`` and now."""
        params = {
            "crtfc_key": self.api_key,
            "bgn_de": since.strftime("%Y%m%d"),
            "end_de": datetime.now().strftime("%Y%m%d"),
            "page_no": page_no,
            "page_count": page_count,
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.get(f"{DART_API_BASE}/list.json", params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Failed to list recent filings: %s", exc)
            raise

        try:
            text = response.content.decode("utf-8")
        except UnicodeDecodeError:
            text = response.content.decode("euc-kr", errors="replace")
        payload = json.loads(text)
        if payload.get("status") != "000":
            message = payload.get("message", "Unknown DART error")
            logger.error("DART returned error status: %s", message)
            raise RuntimeError(f"DART error: {message}")

        filings = payload.get("list", [])
        logger.info("Fetched %d filings between %s and today.", len(filings), since.date())
        return filings

    def download_document_zip(self, receipt_no: str) -> Optional[bytes]:
        """Download the raw filing ZIP payload for a given receipt number."""
        params = {"crtfc_key": self.api_key, "rcept_no": receipt_no}
        try:
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                response = client.get(DOCUMENT_URL, params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Failed to download document for %s: %s", receipt_no, exc)
            raise

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
        return f"http://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}"

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
            raise

        try:
            text = response.content.decode("utf-8")
        except UnicodeDecodeError:
            text = response.content.decode("euc-kr", errors="replace")

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            logger.error("Unable to decode DART JSON payload from %s", endpoint)
            raise

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

    def fetch_single_account_detail(self, corp_code: str, bsns_year: int, reprt_code: str) -> Dict[str, Any]:
        """Fetch DE003 (단일회사 전표준재무제표) data."""
        return self._get_json(
            "fnlttSinglAcntAll.json",
            {"corp_code": corp_code, "bsns_year": str(bsns_year), "reprt_code": reprt_code},
        )

    def fetch_major_shareholders(self, corp_code: str, bsns_year: int, reprt_code: str) -> Dict[str, Any]:
        """Fetch DE004 (임원·주요주주 현황) dataset."""
        return self._get_json(
            "majorstock.json",
            {"corp_code": corp_code, "bsns_year": str(bsns_year), "reprt_code": reprt_code},
        )

    def fetch_major_issues(self, corp_code: str, bsns_year: int, reprt_code: Optional[str] = None) -> Dict[str, Any]:
        """Fetch DE005 (주요사항 보고) dataset."""
        params: Dict[str, Any] = {"corp_code": corp_code, "bsns_year": str(bsns_year)}
        if reprt_code:
            params["reprt_code"] = reprt_code
        return self._get_json("majorissue.json", params)


__all__ = ["DartClient"]
