"""Build crno master map using DART company API (corp_code -> jurir_no)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from database import SessionLocal
from models.security_metadata import SecurityMetadata

API_KEY = os.getenv("DART_API_KEY")
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "configs" / "crno_master_map.json"
BASE_URL = "https://opendart.fss.or.kr/api/company.json"


def build_crno_map() -> int:
    if not API_KEY:
        raise SystemExit("DART_API_KEY is not set.")

    session = SessionLocal()
    rows = (
        session.query(SecurityMetadata.ticker, SecurityMetadata.corp_name, SecurityMetadata.corp_code)
        .filter(SecurityMetadata.ticker.isnot(None))
        .filter(SecurityMetadata.corp_code.isnot(None))
        .all()
    )
    session.close()
    if not rows:
        raise SystemExit("security_metadata is empty or corp_code missing.")

    client = httpx.Client(timeout=httpx.Timeout(5.0, connect=3.0))
    payload = []
    ok = 0
    fail = 0
    try:
        for ticker, name, corp_code in rows:
            params = {"crtfc_key": API_KEY, "corp_code": corp_code}
            try:
                resp = client.get(BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                fail += 1
                print(f"[fail http] ticker={ticker} corp_code={corp_code} err={exc}")
                continue
            jurir_no = str(data.get("jurir_no") or "").strip()
            if len(jurir_no) != 13 or jurir_no == "0000000000000":
                fail += 1
                print(f"[skip jurir_no] ticker={ticker} corp_code={corp_code} status={data.get('status')} msg={data.get('message')} jurir_no={jurir_no}")
                continue
            payload.append(
                {
                    "ticker": ticker,
                    "name": name or ticker,
                    "crno": jurir_no,
                    "corp_code": corp_code,
                }
            )
            ok += 1
    finally:
        client.close()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {ok} records to {OUTPUT_PATH}, failures={fail}")
    return ok


if __name__ == "__main__":
    build_crno_map()
