"""샘플링된 공시 문서 매니페스트를 생성하는 도구."""

from __future__ import annotations

import argparse
import json
import logging
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from scripts._path import add_root

add_root()

from database import SessionLocal
from sqlalchemy import text
from scripts.qa.utils import coerce_int, format_datetime, load_chunks, load_urls

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

SAMPLES_DIR = Path("scripts/qa/samples")


def _chunk_stats(chunks: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    per_source: Dict[str, int] = defaultdict(int)
    span_lengths: List[int] = []

    for chunk in chunks:
        source = chunk.get("source") or (chunk.get("metadata") or {}).get("source")
        normalized_source = str(source or "unknown").lower()
        per_source[normalized_source] += 1

        start = coerce_int(chunk.get("char_start") or (chunk.get("metadata") or {}).get("char_start"))
        end = coerce_int(chunk.get("char_end") or (chunk.get("metadata") or {}).get("char_end"))
        if start is not None and end is not None and end >= start:
            span_lengths.append(end - start)

    total = sum(per_source.values())
    avg_span = (sum(span_lengths) / len(span_lengths)) if span_lengths else None
    return {
        "total": total,
        "sources": dict(sorted(per_source.items(), key=lambda item: item[0])),
        "avg_span": avg_span,
    }


def _classify_variant(per_source: Dict[str, int]) -> str:
    if not per_source:
        return "unknown"
    has_ocr = any("ocr" in key for key in per_source)
    has_pdf = any(key in {"pdf", "text"} for key in per_source)
    if has_ocr and has_pdf:
        return "ocr_mixed"
    if has_ocr and not has_pdf:
        return "ocr_only"
    return "pdf_only"


@dataclass
class FilingSample:
    document_id: str
    receipt_no: Optional[str]
    corp_name: Optional[str]
    ticker: Optional[str]
    report_name: Optional[str]
    source_variant: str
    chunk_count: int
    chunk_sources: Dict[str, int]
    avg_chunk_span: Optional[float]
    filed_at: Optional[str]
    ingested_at: Optional[str]
    file_path: Optional[str]
    download_url: Optional[str]


def _build_filing_sample(payload: Mapping[str, Any], min_chunks: int) -> Optional[FilingSample]:
    chunks = load_chunks(payload.get("chunks"))
    stats = _chunk_stats(chunks)
    if stats["total"] < min_chunks:
        return None

    variant = _classify_variant(stats["sources"])
    urls = load_urls(payload.get("urls"))
    return FilingSample(
        document_id=str(payload.get("id")),
        receipt_no=payload.get("receipt_no"),
        corp_name=payload.get("corp_name"),
        ticker=payload.get("ticker"),
        report_name=payload.get("report_name") or payload.get("title"),
        source_variant=variant,
        chunk_count=stats["total"],
        chunk_sources=stats["sources"],
        avg_chunk_span=stats["avg_span"],
        filed_at=format_datetime(payload.get("filed_at")),
        ingested_at=format_datetime(payload.get("updated_at")),
        file_path=payload.get("file_path"),
        download_url=urls.get("download"),
    )


FILING_QUERY = text(
    """
    SELECT
        id,
        receipt_no,
        corp_name,
        ticker,
        report_name,
        title,
        filed_at,
        updated_at,
        file_path,
        urls,
        chunks,
        created_at
    FROM filings
    WHERE chunks IS NOT NULL
    ORDER BY filed_at DESC NULLS LAST, created_at DESC
    LIMIT :limit
    """
)


def collect_filing_samples(
    session,
    total: int,
    min_chunks: int,
    min_ocr: int,
    seed: int,
    candidate_pool: int,
) -> List[FilingSample]:
    rows = session.execute(FILING_QUERY, {"limit": max(candidate_pool, total * 2)}).all()

    candidates: List[FilingSample] = []
    for row in rows:
        sample = _build_filing_sample(row._mapping, min_chunks=min_chunks)  # type: ignore[attr-defined]
        if sample:
            candidates.append(sample)

    if not candidates:
        raise RuntimeError("샘플링 가능한 공시 문서를 찾지 못했습니다.")

    rng = random.Random(seed)
    rng.shuffle(candidates)

    selected: List[FilingSample] = []
    ocr_candidates = [sample for sample in candidates if sample.source_variant.startswith("ocr")]
    if min_ocr > 0 and ocr_candidates:
        take = min(min_ocr, len(ocr_candidates))
        selected.extend(ocr_candidates[:take])

    remaining = [sample for sample in candidates if sample not in selected]
    rng.shuffle(remaining)
    for sample in remaining:
        if len(selected) >= total:
            break
        selected.append(sample)

    if len(selected) < total:
        logger.warning("요청 수(%d)보다 적은 %d개만 확보했습니다.", total, len(selected))

    return selected


def build_manifest(
    samples: Sequence[FilingSample],
    filters: Dict[str, Any],
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    variant_counts = Counter(sample.source_variant for sample in samples)

    documents = [asdict(sample) for sample in samples]
    return {
        "generated_at": generated_at,
        "total_entries": len(samples),
        "filters": filters,
        "summary": {
            "variant_breakdown": dict(variant_counts),
            "avg_chunk_count": (sum(sample.chunk_count for sample in samples) / len(samples)) if samples else None,
        },
        "notes": notes or "Generated via scripts/qa/sample_documents.py",
        "documents": documents,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="QA를 위한 공시 문서 샘플 manifest 생성기")
    parser.add_argument(
        "--total",
        type=int,
        default=60,
        help="생성할 샘플 문서 수 (기본: 60, 최소: 10)",
    )
    parser.add_argument(
        "--min-chunks",
        type=int,
        default=10,
        help="포함할 최소 chunk 수 (기본: 10)",
    )
    parser.add_argument(
        "--min-ocr",
        type=int,
        default=15,
        help="OCR chunk를 포함한 최소 문서 수 (기본: 15)",
    )
    parser.add_argument(
        "--candidate-pool",
        type=int,
        default=400,
        help="DB에서 불러올 후보 문서 수 (기본: 400)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="샘플링에 사용할 시드 값",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="결과를 저장할 경로 (지정하지 않으면 scripts/qa/samples/manifest_<timestamp>.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="파일을 저장하지 않고 요약만 출력",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.total < 10:
        raise ValueError("샘플 수는 최소 10개 이상이어야 합니다.")

    session = SessionLocal()
    try:
        samples = collect_filing_samples(
            session=session,
            total=args.total,
            min_chunks=args.min_chunks,
            min_ocr=args.min_ocr,
            seed=args.seed,
            candidate_pool=args.candidate_pool,
        )
    finally:
        session.close()

    filters = {
        "total": args.total,
        "min_chunks": args.min_chunks,
        "min_ocr": args.min_ocr,
        "candidate_pool": args.candidate_pool,
        "seed": args.seed,
    }
    manifest = build_manifest(samples, filters=filters)

    if args.dry_run:
        logger.info("생성된 매니페스트 (dry-run):")
        logger.info(json.dumps(manifest, ensure_ascii=False, indent=2))
        return

    target_path = args.output
    if target_path is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target_path = SAMPLES_DIR / f"manifest_{timestamp}.json"
    target_path.parent.mkdir(parents=True, exist_ok=True)

    target_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("샘플 %d개를 %s에 저장했습니다.", len(samples), target_path)


if __name__ == "__main__":
    main()
