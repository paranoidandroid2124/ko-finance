"""Client for interacting with the DART OpenAPI."""

from __future__ import annotations

import io
import logging
import os
import zipfile
from datetime import datetime
from typing import Dict, List, Optional

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

        payload = response.json()
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
        if "zip" in content_type or response.content.startswith(b"PK"):
            return response.content

        try:
            payload = xmltodict.parse(response.text)
            message = payload.get("result", {}).get("message", "Unknown error")
        except Exception:
            message = response.text
        logger.warning("DART document download returned non-ZIP content (%s): %s", receipt_no, message)
        return None

    @staticmethod
    def make_viewer_url(receipt_no: str) -> str:
        return f"http://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}"

    @staticmethod
    def make_document_url(receipt_no: str) -> str:
        return f"{DOCUMENT_URL}?rcept_no={receipt_no}"


__all__ = ["DartClient"]

