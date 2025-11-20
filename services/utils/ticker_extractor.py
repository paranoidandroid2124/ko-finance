"""Lightweight ticker/name/crno extractor for Korean equities."""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from database import SessionLocal
from models.security_metadata import SecurityMetadata

# Fallback alias map (used if master map unavailable)
ALIAS_MAP = {
    "삼성전자": {"ticker": "005930", "crno": None},
    "sk하이닉스": {"ticker": "000660", "crno": None},
    "엘지화학": {"ticker": "051910", "crno": None},
    "카카오": {"ticker": "035720", "crno": None},
    "네이버": {"ticker": "035420", "crno": None},
}

DEFAULT_MAP_PATH = Path(__file__).resolve().parents[1] / "configs" / "crno_master_map.json"
SOURCE = os.getenv("TICKER_EXTRACT_SOURCE", "auto").lower()  # auto|db|file


def _normalize(text: str) -> str:
    return text.strip().lower()


@lru_cache(maxsize=1)
def _load_master_map_from_file() -> list[dict]:
    path_str = os.getenv("CRNO_MASTER_MAP_PATH")
    path = Path(path_str) if path_str else DEFAULT_MAP_PATH
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


@lru_cache(maxsize=1)
def _load_master_map_from_db() -> list[dict]:
    try:
        session = SessionLocal()
    except Exception:
        return []
    try:
        rows = session.query(
            SecurityMetadata.ticker,
            SecurityMetadata.corp_name,
            SecurityMetadata.corp_code,
            SecurityMetadata.market,
            SecurityMetadata.extra,
        ).all()
    except Exception:
        return []
    finally:
        session.close()

    result = []
    for ticker, name, corp_code, market, extra in rows:
        if not ticker:
            continue
        crno = None
        if isinstance(extra, dict):
            crno_candidate = extra.get("crno")
            if isinstance(crno_candidate, str) and crno_candidate.isdigit() and len(crno_candidate) == 13:
                crno = crno_candidate
        if not crno and corp_code and isinstance(corp_code, str) and corp_code.isdigit() and len(corp_code) == 13:
            crno = corp_code
        result.append({"ticker": ticker, "name": name or ticker, "crno": crno, "market": market})
    return result


def _iter_master_records() -> list[dict]:
    if SOURCE in ("db", "auto"):
        db_map = _load_master_map_from_db()
        if db_map:
            return db_map
    if SOURCE in ("file", "auto"):
        file_map = _load_master_map_from_file()
        if file_map:
            return file_map
    return []


def _match_master(normalized_text: str) -> Optional[dict]:
    for item in _iter_master_records():
        if not isinstance(item, dict):
            continue
        name = _normalize(item.get("name", ""))
        ticker = str(item.get("ticker") or "").strip()
        if ticker and ticker in normalized_text:
            return item
        if name and name in normalized_text:
            return item
    return None


def extract_ticker_or_name(text: str) -> Optional[str]:
    if not text:
        return None
    normalized = text.strip()
    match_code = re.search(r"\b(\d{6})\b", normalized)
    if match_code:
        return match_code.group(1)

    master_hit = _match_master(_normalize(normalized))
    if master_hit:
        return master_hit.get("ticker") or master_hit.get("name")

    for alias, info in ALIAS_MAP.items():
        if alias in normalized:
            return info.get("ticker") or alias

    match_alpha = re.search(r"\b([A-Z]{4,5})\b", normalized.upper())
    if match_alpha:
        return match_alpha.group(1)
    return None


def resolve_crno(text: str) -> Optional[str]:
    if not text:
        return None
    normalized = text.strip()
    match_crno = re.search(r"\b(\d{10,13})\b", normalized)
    if match_crno:
        return match_crno.group(1)

    master_hit = _match_master(_normalize(normalized))
    if master_hit:
        candidate = master_hit.get("crno")
        if isinstance(candidate, str) and len(candidate) == 13 and candidate.isdigit() and candidate != "0000000000000":
            return candidate

    for alias, info in ALIAS_MAP.items():
        if alias in normalized:
            crno = info.get("crno")
            if crno:
                return crno
    return None


__all__ = ["extract_ticker_or_name", "resolve_crno"]
