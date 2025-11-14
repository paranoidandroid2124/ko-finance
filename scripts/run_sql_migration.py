#!/usr/bin/env python
"""Utility to apply SQL migration files inside Docker."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable

import psycopg2
from psycopg2.extensions import connection as PGConnection

ROOT_DIR = Path(__file__).resolve().parents[1]


def _resolve_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.getenv("POSTGRES_USER", "kfinance")
    password = os.getenv("POSTGRES_PASSWORD", "your_strong_password")
    host = os.getenv("POSTGRES_SERVER", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "kfinance_db")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def _connect() -> PGConnection:
    url = _resolve_database_url()
    conn = psycopg2.connect(url)
    conn.autocommit = True
    return conn


def _read_sql(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Migration file not found: {path}")
    return path.read_text(encoding="utf-8")


def _run_sql(conn: PGConnection, sql: str, label: str) -> None:
    with conn.cursor() as cursor:
        cursor.execute(sql)
        print(f"[migration] Applied {label}")


def apply_migrations(paths: Iterable[Path]) -> None:
    conn = _connect()
    try:
        for path in paths:
            sql = _read_sql(path)
            _run_sql(conn, sql, path.name)
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply SQL migrations via psycopg2.")
    parser.add_argument(
        "files",
        nargs="+",
        help="Relative or absolute paths to SQL files (run in provided order).",
    )
    args = parser.parse_args()
    file_paths = [Path(f).resolve() if Path(f).is_absolute() else (ROOT_DIR / f).resolve() for f in args.files]
    apply_migrations(file_paths)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"[migration] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
