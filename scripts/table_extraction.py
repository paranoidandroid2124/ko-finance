"""CLI helper for running Table Extraction v1 locally."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._path import add_root

add_root()

from database import SessionLocal
from parse.table_extraction import TableExtractor, TableExtractorError
from services.table_extraction_service import TableExtractionServiceError, run_table_extraction_for_receipt

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("table_extraction_cli")


def _run_for_receipt(args: argparse.Namespace) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        return run_table_extraction_for_receipt(db, args.receipt, pdf_path=args.pdf)
    finally:
        db.close()


def _run_for_file(args: argparse.Namespace) -> Dict[str, Any]:
    time_budget = float(args.time_budget) if args.time_budget else None
    extractor = TableExtractor(
        max_pages=args.max_pages,
        max_tables=args.max_tables,
        time_budget_seconds=time_budget or 90.0,
    )
    results = extractor.extract(args.file)

    output_dir = Path(args.output or "reports/table_extraction/manual")
    output_dir.mkdir(parents=True, exist_ok=True)

    for result in results:
        prefix = output_dir / f"page{result.page_number:03d}_table{result.table_index:02d}"
        prefix.with_suffix(".html").write_text(result.html, encoding="utf-8")
        prefix.with_suffix(".csv").write_text(result.csv, encoding="utf-8")
        prefix.with_suffix(".json").write_text(
            json.dumps(result.json_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return {
        "tables": len(results),
        "output_dir": str(output_dir),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Table Extraction v1 pipeline.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--receipt", help="DART receipt number to reprocess.")
    group.add_argument("--file", help="Local PDF path for ad-hoc extraction.")
    parser.add_argument("--pdf", help="Override PDF path when using --receipt.")
    parser.add_argument("--max-pages", type=int, default=None, help="Optional override for scanned pages.")
    parser.add_argument("--max-tables", type=int, default=None, help="Optional override for maximum tables.")
    parser.add_argument("--time-budget", type=int, default=None, help="Optional override for time budget (seconds).")
    parser.add_argument("--output", help="Directory for artifacts when running with --file.")
    parser.add_argument("--json", action="store_true", help="Print JSON summary to stdout.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if args.receipt:
            stats = _run_for_receipt(args)
        else:
            stats = _run_for_file(args)
    except (TableExtractionServiceError, TableExtractorError) as exc:
        logger.error("Table extraction failed: %s", exc)
        raise SystemExit(1) from exc

    if args.json:
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    else:
        logger.info("Table extraction summary: %s", stats)


if __name__ == "__main__":
    main()
