#!/usr/bin/env python
"""Apply the RAG grid job migration."""

from __future__ import annotations

from pathlib import Path

from scripts.run_sql_migration import apply_migrations

MIGRATION_FILE = Path(__file__).resolve().parents[1] / "ops" / "migrations" / "20251115_add_rag_grid_jobs.sql"


def main() -> None:
    apply_migrations([MIGRATION_FILE])


if __name__ == "__main__":
    main()
