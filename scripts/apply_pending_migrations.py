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
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)

    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB")
    if not all((user, password, db)):
        raise SystemExit("Set DATABASE_URL or POSTGRES_* environment variables.")
    return psycopg2.connect(
        dbname=db,
        user=user,
        password=password,
        host=host,
        port=port,
    )


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
