"""Backfill security_metadata.extra with sector info from a CSV mapping.

Usage:
  python scripts/backfill_security_sector.py [path/to/sector_map.csv]

CSV format (header required):
  ticker,sector,sector_name
  005930,semiconductor,반도체
  000660,semiconductor,반도체
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Dict, Tuple

from database import SessionLocal
from models.security_metadata import SecurityMetadata


def load_mapping(path: Path) -> Dict[str, Tuple[str, str]]:
    mapping: Dict[str, Tuple[str, str]] = {}
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ticker = (row.get("ticker") or "").strip().upper()
            sector = (row.get("sector") or "").strip()
            sector_name = (row.get("sector_name") or "").strip()
            if not ticker or not sector:
                continue
            mapping[ticker] = (sector, sector_name or sector)
    return mapping


def backfill(path: Path) -> int:
    mapping = load_mapping(path)
    if not mapping:
        print("No mapping entries found; aborting.")
        return 0

    updated = 0
    with SessionLocal() as db:
        rows = db.query(SecurityMetadata).filter(SecurityMetadata.ticker.in_(list(mapping.keys()))).all()
        for row in rows:
            sector_slug, sector_name = mapping.get(row.ticker, (None, None))
            if not sector_slug:
                continue
            extra = row.extra or {}
            extra["sector"] = sector_slug
            extra.setdefault("sector_name", sector_name)
            row.extra = extra
            updated += 1
        if updated:
            db.commit()
    return updated


if __name__ == "__main__":
    file_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("configs/sector_map.csv")
    if not file_path.exists():
        print(f"Mapping file not found: {file_path}")
        sys.exit(1)
    count = backfill(file_path)
    print(f"Updated {count} rows.")
