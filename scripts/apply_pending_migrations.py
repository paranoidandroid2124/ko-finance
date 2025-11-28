#!/usr/bin/env python
"""Apply every SQL migration under ops/migrations exactly once."""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

import psycopg2
from psycopg2.extensions import connection as PGConnection

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_PATH = ROOT / "ops" / "migrations"
TABLE_NAME = "schema_migrations"


def discover_migrations() -> list[Path]:
    files = sorted(path for path in MIGRATIONS_PATH.glob("*.sql") if path.is_file())
    if not files:
        raise SystemExit("No migrations found under ops/migrations.")
    return files


def connect() -> PGConnection:
    """Connect to database using DATABASE_URL.
    
    DATABASE_URL 환경 변수를 사용합니다 (Supabase 권장).
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit(
            "DATABASE_URL 환경 변수가 설정되어 있어야 합니다.\n"
            "형식: postgresql://user:password@host:port/database"
        )
    return psycopg2.connect(database_url)


def ensure_tracking_table(cur) -> None:
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            filename TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


def fetch_applied(cur) -> set[str]:
    cur.execute(f"SELECT filename FROM {TABLE_NAME}")
    rows = cur.fetchall()
    return {row[0] for row in rows}


def apply_migration(cur, migration: Path) -> None:
    sql = migration.read_text(encoding="utf-8")
    cur.execute(sql)
    cur.execute(
        f"INSERT INTO {TABLE_NAME} (filename, applied_at) VALUES (%s, %s)",
        (migration.name, datetime.utcnow()),
    )


def main() -> None:
    migrations = discover_migrations()
    with connect() as conn:
        conn.autocommit = False
        with conn.cursor() as cur:
            ensure_tracking_table(cur)
            applied = fetch_applied(cur)
            pending = [m for m in migrations if m.name not in applied]
            if not pending:
                print("✅ No pending migrations.")
                return
            for migration in pending:
                print(f"▶ Applying {migration.name}")
                apply_migration(cur, migration)
            conn.commit()
            print(f"✅ Applied {len(pending)} migration(s).")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - operational script
        print(f"❌ Migration failed: {exc}", file=sys.stderr)
        sys.exit(1)
