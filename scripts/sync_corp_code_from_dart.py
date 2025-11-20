"""Sync DART corp_code (8-digit) into security_metadata from corpCode.xml."""

from __future__ import annotations

import io
import os
import zipfile
import logging
import xml.etree.ElementTree as ET

import requests

from database import SessionLocal
from models.security_metadata import SecurityMetadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("DART_API_KEY")
ENDPOINT = "https://opendart.fss.or.kr/api/corpCode.xml"


def _normalize_name(value: str) -> str:
    return (value or "").replace(" ", "").replace(".", "").strip().lower()


def _candidate_bases(ticker: str) -> list[str]:
    bases: list[str] = []
    if not ticker:
        return bases
    ticker = ticker.strip()
    if len(ticker) >= 6:
        bases.append(ticker[:6])
    if len(ticker) == 6 and ticker[-1].isdigit():
        bases.append(ticker[:-1] + "0")
    if len(ticker) == 6 and ticker[-1].isalpha():
        bases.append(ticker[:5] + "0")
    return list(dict.fromkeys(bases))


def sync_corp_code_from_dart() -> int:
    if not API_KEY:
        logger.error("DART_API_KEY not set; aborting.")
        return 0

    try:
        resp = requests.get(f"{ENDPOINT}?crtfc_key={API_KEY}", timeout=30)
        resp.raise_for_status()
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("Failed to download corpCode.xml: %s", exc)
        return 0

    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            with zf.open("CORPCODE.xml") as fp:
                tree = ET.parse(fp)
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to parse corpCode.xml: %s", exc)
        return 0

    root = tree.getroot()
    mapping: dict[str, str] = {}
    name_map: dict[str, str] = {}
    base_map: dict[str, str] = {}
    for elem in root.iter("list"):
        stock = (elem.findtext("stock_code") or "").strip()
        corp_code = (elem.findtext("corp_code") or "").strip()
        corp_name = (elem.findtext("corp_name") or "").strip()
        if corp_name:
            name_map[_normalize_name(corp_name)] = corp_code
        if stock and corp_code:
            mapping[stock] = corp_code
            base_map[stock[:6]] = corp_code  # 보통주 코드로 매핑

    if not mapping:
        logger.warning("No stock_code -> corp_code mapping found in corpCode.xml")
        return 0

    session = SessionLocal()
    updated = 0
    try:
        rows = session.query(SecurityMetadata).filter(SecurityMetadata.ticker.isnot(None)).all()
        for row in rows:
            corp_code = mapping.get(row.ticker)
            if not corp_code and row.ticker:
                for base in _candidate_bases(row.ticker):
                    corp_code = mapping.get(base) or base_map.get(base)
                    if corp_code:
                        break
            if not corp_code and row.corp_name:
                corp_code = name_map.get(_normalize_name(row.corp_name))
            if corp_code and row.corp_code != corp_code:
                row.corp_code = corp_code
                updated += 1
        if updated:
            session.commit()
            logger.info("Updated corp_code for %s tickers.", updated)
        else:
            logger.info("No corp_code updates applied.")
    finally:
        session.close()

    return updated


if __name__ == "__main__":
    sync_corp_code_from_dart()
