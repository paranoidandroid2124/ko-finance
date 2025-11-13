"""Run structural validation + QA metrics for Table Extraction v1."""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts._path import add_root

add_root()

from parse.table_extraction import TableExtractor, TableExtractorError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("table_extraction_eval")

DEFAULT_OUTPUT = Path("reports/table_extraction/quality_report.json")


CORE_FIELD_KEYWORDS: Dict[str, List[str]] = {
    "dividend": ["배당", "주당", "배당률"],
    "treasury": ["자사주", "취득", "처분"],
    "cb_bw": ["전환", "사채", "권리"],
    "financials": ["자산", "부채", "손익"],
}


def _core_accuracy(table_type: Optional[str], header_paths: Optional[List[List[str]]]) -> float:
    if not table_type:
        return 1.0
    keywords = CORE_FIELD_KEYWORDS.get(table_type)
    if not keywords:
        return 1.0
    flattened = [" ".join(path) for path in (header_paths or []) if path]
    if not flattened:
        return 0.0
    hits = 0
    for keyword in keywords:
        if any(keyword in header for header in flattened):
            hits += 1
    return hits / len(keywords)


def _validate_table(table_payload: Dict[str, Any]) -> Dict[str, Any]:
    stats = table_payload.get("stats") or {}
    header_coverage = float(stats.get("headerCoverage") or 0.0)
    non_empty_ratio = float(stats.get("nonEmptyRatio") or 0.0)
    numeric_ratio = float(stats.get("numericRatio") or 0.0)
    core_acc = _core_accuracy(table_payload.get("table_type"), table_payload.get("headerPaths"))

    checks = {
        "header_rows": stats.get("headerRows", 0) >= 1,
        "header_coverage": header_coverage >= 0.75,
        "non_empty": non_empty_ratio >= 0.85,
        "core_fields": core_acc >= 0.9,
        "numeric_density": numeric_ratio >= 0.0,
    }
    passed = all(checks.values())
    accuracy_score = round((0.5 * header_coverage) + (0.3 * non_empty_ratio) + (0.2 * core_acc), 4)
    return {
        "passed": passed,
        "checks": checks,
        "headerCoverage": header_coverage,
        "nonEmptyRatio": non_empty_ratio,
        "numericRatio": numeric_ratio,
        "coreAccuracy": round(core_acc, 4),
        "accuracyScore": accuracy_score,
        "tableType": table_payload.get("table_type"),
        "title": table_payload.get("title"),
    }


def _collect_pdfs(root: Path) -> List[Path]:
    return [path for path in root.rglob("*.pdf") if path.is_file()]


def run_evaluation(args: argparse.Namespace) -> Dict[str, Any]:
    root = Path(args.input or "uploads")
    files = _collect_pdfs(root)
    if not files:
        raise RuntimeError(f"No PDF files found under {root}")

    rng = random.Random(args.seed)
    rng.shuffle(files)
    sample = files[: args.samples]

    extractor = TableExtractor(
        max_pages=args.max_pages,
        max_tables=args.max_tables,
        time_budget_seconds=args.time_budget,
    )

    table_records: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []

    for pdf_path in sample:
        try:
            tables = extractor.extract(str(pdf_path))
        except TableExtractorError as exc:
            logger.warning("Extraction failed for %s: %s", pdf_path, exc)
            continue
        for table in tables:
            if table.stats.get("rowCount", 0) <= 0:
                continue
            payload = {
                "file": str(pdf_path),
                "page": table.page_number,
                "tableIndex": table.table_index,
                "table_type": table.table_type,
                "stats": table.stats,
                "title": table.title,
                "confidence": table.confidence,
                "headerPaths": table.header_paths,
            }
            result = _validate_table(payload)
            table_records.append({**payload, **result})
            if not result["passed"]:
                failures.append({**payload, **result})

    total_tables = len(table_records)
    passed_tables = sum(1 for record in table_records if record["passed"])
    avg_header = sum(record["headerCoverage"] for record in table_records) / total_tables if total_tables else 0.0
    avg_non_empty = sum(record["nonEmptyRatio"] for record in table_records) / total_tables if total_tables else 0.0
    avg_core = sum(record.get("coreAccuracy", 0.0) for record in table_records) / total_tables if total_tables else 0.0
    avg_accuracy = sum(record["accuracyScore"] for record in table_records) / total_tables if total_tables else 0.0

    summary = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "pdfRoot": str(root),
        "sampleSize": len(sample),
        "tableCount": total_tables,
        "passRate": round(passed_tables / total_tables, 4) if total_tables else 0.0,
        "avgHeaderCoverage": round(avg_header, 4),
        "avgNonEmptyRatio": round(avg_non_empty, 4),
        "avgCoreAccuracy": round(avg_core, 4),
        "avgAccuracyScore": round(avg_accuracy, 4),
        "targetPassRate": 0.90,
        "config": {
            "maxPages": args.max_pages,
            "maxTables": args.max_tables,
            "timeBudget": args.time_budget,
        },
        "failures": failures[: args.max_failures],
    }
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate QA metrics for Table Extraction v1.")
    parser.add_argument("--input", help="Root directory containing sample PDFs (default: uploads).")
    parser.add_argument("--samples", type=int, default=50, help="Number of PDF documents to sample.")
    parser.add_argument("--seed", type=int, default=17, help="Sampling seed to keep evaluations reproducible.")
    parser.add_argument("--max-pages", type=int, default=15, help="Max pages to scan per PDF.")
    parser.add_argument("--max-tables", type=int, default=60, help="Max tables to retain per document.")
    parser.add_argument("--time-budget", type=float, default=90.0, help="Time budget in seconds per document.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Path to write the QA report JSON.")
    parser.add_argument("--max-failures", type=int, default=20, help="Max failing samples to include in the report.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary = run_evaluation(args)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "QA report written to %s (pass rate=%.3f, tables=%d).",
        output_path,
        summary["passRate"],
        summary["tableCount"],
    )


if __name__ == "__main__":
    main()
