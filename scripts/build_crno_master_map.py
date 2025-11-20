"""Build a master map of ticker/name/crno from SecurityMetadata."""

from __future__ import annotations

import json
from pathlib import Path

from database import SessionLocal
from models.security_metadata import SecurityMetadata


OUTPUT_PATH = Path(__file__).resolve().parents[1] / "configs" / "crno_master_map.json"


def build_crno_map() -> int:
    session = SessionLocal()
    try:
        rows = (
            session.query(
                SecurityMetadata.ticker,
                SecurityMetadata.corp_name,
                SecurityMetadata.corp_code,
                SecurityMetadata.market,
            )
            .filter(SecurityMetadata.ticker.isnot(None))
            .all()
        )
    finally:
        session.close()

    payload = []
    for row in rows:
        ticker = row.ticker
        if not ticker:
            continue
        payload.append(
            {
                "ticker": ticker,
                "name": row.corp_name or ticker,
                "crno": row.corp_code,
                "market": row.market,
            }
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(payload)} records to {OUTPUT_PATH}")
    return len(payload)


if __name__ == "__main__":
    build_crno_map()
