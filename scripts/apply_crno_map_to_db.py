"""Apply crno master map to security_metadata (store in extra.crno)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from database import SessionLocal
from models.security_metadata import SecurityMetadata

DEFAULT_MAP_PATH = Path(__file__).resolve().parents[1] / "configs" / "crno_master_map.json"


def apply_crno_map(map_path: Path = DEFAULT_MAP_PATH) -> int:
    if not map_path.is_file():
        raise SystemExit(f"crno map not found: {map_path}")

    data = json.loads(map_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit("crno map must be a list of objects.")

    by_ticker: Dict[str, str] = {}
    by_corp_code: Dict[str, str] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        crno = str(item.get("crno") or "").strip()
        if not (crno.isdigit() and len(crno) == 13 and crno != "0000000000000"):
            continue
        ticker = str(item.get("ticker") or "").strip()
        corp_code = str(item.get("corp_code") or "").strip()
        if ticker:
            by_ticker[ticker] = crno
        if corp_code:
            by_corp_code[corp_code] = crno

    session = SessionLocal()
    updated = 0
    try:
        rows = session.query(SecurityMetadata).filter(SecurityMetadata.ticker.isnot(None)).all()
        for row in rows:
            crno = by_ticker.get(row.ticker) or by_corp_code.get(row.corp_code or "")
            if not crno:
                continue
            extras = row.extra or {}
            if extras.get("crno") == crno:
                continue
            extras["crno"] = crno
            row.extra = extras
            updated += 1
        if updated:
            session.commit()
            print(f"Updated crno for {updated} tickers using {map_path}")
        else:
            print("No crno updates applied.")
    finally:
        session.close()
    return updated


if __name__ == "__main__":
    apply_crno_map()
