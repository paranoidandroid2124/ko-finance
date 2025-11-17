#!/usr/bin/env python
"""Utility to apply SQL migration files inside Docker.

If no 파일을 직접 지정하지 않으면 ``ops/migrations`` 아래의 SQL 파일을
정렬된 순서로 훑어서 아직 적용되지 않은 항목만 실행하고,
``schema_migrations`` 메타테이블에 기록합니다.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List

import psycopg2
from psycopg2.extensions import connection as PGConnection

ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MIGRATIONS_DIR = ROOT_DIR / "ops" / "migrations"
MIGRATION_TABLE = "schema_migrations"


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


def _ensure_migration_table(conn: PGConnection) -> None:
    ddl = f"""
    CREATE TABLE IF NOT EXISTS {MIGRATION_TABLE} (
        filename TEXT PRIMARY KEY,
        checksum TEXT NOT NULL,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """
    with conn.cursor() as cursor:
        cursor.execute(ddl)


def _load_applied_migrations(conn: PGConnection) -> Dict[str, str]:
    with conn.cursor() as cursor:
        cursor.execute(f"SELECT filename, checksum FROM {MIGRATION_TABLE}")
        rows = cursor.fetchall()
    return {filename: checksum for filename, checksum in rows}


def _record_migration(conn: PGConnection, filename: str, checksum: str) -> None:
    with conn.cursor() as cursor:
        cursor.execute(
            f"""
            INSERT INTO {MIGRATION_TABLE} (filename, checksum)
            VALUES (%s, %s)
            ON CONFLICT (filename) DO UPDATE SET checksum = EXCLUDED.checksum
            """,
            (filename, checksum),
        )


def _checksum(sql: str) -> str:
    return hashlib.sha256(sql.encode("utf-8")).hexdigest()


def _list_sql_files(directory: Path) -> List[Path]:
    if not directory.exists():
        return []
    return sorted(p for p in directory.iterdir() if p.suffix.lower() == ".sql")


def _resolve_paths(files: List[str]) -> List[Path]:
    resolved = []
    for entry in files:
        path = Path(entry)
        if not path.is_absolute():
            path = (ROOT_DIR / entry).resolve()
        resolved.append(path)
    return resolved


def apply_migrations(paths: Iterable[Path], *, dry_run: bool = False) -> None:
    conn = _connect()
    try:
        _ensure_migration_table(conn)
        applied = _load_applied_migrations(conn)
        pending: List[Path] = []
        for path in paths:
            sql = _read_sql(path)
            checksum = _checksum(sql)
            recorded = applied.get(path.name)
            if recorded:
                if recorded != checksum:
                    raise RuntimeError(
                        f"Checksum mismatch for {path.name}. "
                        "이미 적용된 파일이 수정되었습니다."
                    )
                print(f"[migration] Skipping already applied file {path.name}")
                continue
            pending.append(path)
            if dry_run:
                continue
            _run_sql(conn, sql, path.name)
            _record_migration(conn, path.name, checksum)

        if dry_run:
            if pending:
                print("[migration] Pending files:")
                for path in pending:
                    print(f"  - {path}")
            else:
                print("[migration] No pending migrations.")
        else:
            if pending:
                print(f"[migration] Applied {len(pending)} new migration(s).")
            else:
                print("[migration] All migrations were already applied.")
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply SQL migrations via psycopg2.")
    parser.add_argument(
        "files",
        nargs="*",
        help="상대/절대 경로. 생략하면 ops/migrations 디렉터리의 미적용 파일을 순서대로 실행합니다.",
    )
    parser.add_argument(
        "--migrations-dir",
        default=str(DEFAULT_MIGRATIONS_DIR),
        help="자동 모드에서 사용할 마이그레이션 디렉터리 (기본: ops/migrations).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제로 적용하지 않고 어떤 파일이 실행될지 출력만 합니다.",
    )
    args = parser.parse_args()

    if args.files:
        file_paths = _resolve_paths(args.files)
    else:
        migrations_dir = Path(args.migrations_dir)
        file_paths = _list_sql_files(migrations_dir)
        if not file_paths:
            print(f"[migration] No SQL files found in {migrations_dir}")
            return

    apply_migrations(file_paths, dry_run=args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - CLI guard
        print(f"[migration] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
