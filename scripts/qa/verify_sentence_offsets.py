"""샘플 매니페스트를 기반으로 sentence hash/offset 정합성을 검증하는 도구."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from scripts._path import add_root

add_root()

from database import SessionLocal  # noqa: E402  pylint: disable=wrong-import-position
from parse.chunk_utils import normalize_text  # noqa: E402  pylint: disable=wrong-import-position
from sqlalchemy import text  # noqa: E402  pylint: disable=wrong-import-position
from scripts.qa.utils import coerce_int, load_chunks  # noqa: E402  pylint: disable=wrong-import-position

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

DEFAULT_REPORT_DIR = Path("reports/qa")
DEFAULT_REPORT_DIR.mkdir(parents=True, exist_ok=True)


def sentence_hash(text: str) -> Optional[str]:
    normalized = normalize_text(text) if text else ""
    if not normalized:
        return None
    return hashlib.sha1(normalized.encode("utf-8", errors="ignore")).hexdigest()


def load_manifest(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if "documents" not in data or not isinstance(data["documents"], list):
        raise ValueError("매니페스트에 documents 배열이 필요합니다.")
    return data


def get_metadata(chunk: Dict[str, Any]) -> Dict[str, Any]:
    metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), dict) else {}
    return metadata


def extract_text(chunk: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    for key in ("content", "quote", "text"):
        value = chunk.get(key)
        if isinstance(value, str) and value.strip():
            return value
    value = metadata.get("quote")
    if isinstance(value, str):
        return value
    return ""


@dataclass
class ChunkIssue:
    chunk_id: str
    issue_type: str
    details: Dict[str, Any]


@dataclass
class DocumentResult:
    document_id: str
    receipt_no: Optional[str]
    chunk_count: int
    issues: List[ChunkIssue]


def verify_chunk(chunk: Dict[str, Any]) -> List[ChunkIssue]:
    metadata = get_metadata(chunk)
    issues: List[ChunkIssue] = []
    chunk_id = str(
        chunk.get("chunk_id")
        or chunk.get("id")
        or metadata.get("chunk_id")
        or metadata.get("id")
        or "unknown"
    )

    text = extract_text(chunk, metadata)
    normalized = normalize_text(text) if text else ""
    expected_hash = sentence_hash(text) if text else None
    recorded_hash = metadata.get("sentence_hash") or chunk.get("sentence_hash")

    if normalized and not recorded_hash:
        issues.append(ChunkIssue(chunk_id=chunk_id, issue_type="missing_hash", details={"text_preview": normalized[:80]}))
    elif normalized and recorded_hash and expected_hash and recorded_hash != expected_hash:
        issues.append(
            ChunkIssue(
                chunk_id=chunk_id,
                issue_type="hash_mismatch",
                details={
                    "expected": expected_hash,
                    "recorded": recorded_hash,
                    "text_preview": normalized[:80],
                },
            )
        )

    char_start = coerce_int(chunk.get("char_start") or metadata.get("char_start"))
    char_end = coerce_int(chunk.get("char_end") or metadata.get("char_end"))

    if char_start is None or char_end is None:
        if normalized:
            issues.append(
                ChunkIssue(
                    chunk_id=chunk_id,
                    issue_type="missing_offsets",
                    details={},
                )
            )
    else:
        if char_end < char_start:
            issues.append(
                ChunkIssue(
                    chunk_id=chunk_id,
                    issue_type="offset_negative",
                    details={"char_start": char_start, "char_end": char_end},
                )
            )
        else:
            span = char_end - char_start
            expected_length = len(text or "")
            tolerance = max(2, int(expected_length * 0.05))
            if expected_length > 0 and abs(span - expected_length) > tolerance:
                issues.append(
                    ChunkIssue(
                        chunk_id=chunk_id,
                        issue_type="offset_length_mismatch",
                        details={
                            "span": span,
                            "expected": expected_length,
                            "char_start": char_start,
                            "char_end": char_end,
                        },
                    )
                )

    return issues


FETCH_FILING_BY_ID = text(
    """
    SELECT id, receipt_no, chunks
    FROM filings
    WHERE id = :id
    LIMIT 1
    """
)

FETCH_FILING_BY_RECEIPT = text(
    """
    SELECT id, receipt_no, chunks
    FROM filings
    WHERE receipt_no = :receipt_no
    LIMIT 1
    """
)


def fetch_filing(session, document_entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    document_id = document_entry.get("document_id")
    receipt_no = document_entry.get("receipt_no")
    if document_id:
        try:
            doc_uuid = str(uuid.UUID(str(document_id)))
        except ValueError:
            doc_uuid = None
        if doc_uuid:
            row = session.execute(FETCH_FILING_BY_ID, {"id": doc_uuid}).first()
            if row:
                return dict(row._mapping)  # type: ignore[attr-defined]
    if receipt_no:
        row = session.execute(FETCH_FILING_BY_RECEIPT, {"receipt_no": receipt_no}).first()
        if row:
            return dict(row._mapping)  # type: ignore[attr-defined]
    return None


def evaluate_documents(
    manifest_docs: Sequence[Dict[str, Any]],
    max_docs: Optional[int],
) -> Tuple[List[DocumentResult], Counter]:
    session = SessionLocal()
    issue_counter: Counter = Counter()
    results: List[DocumentResult] = []

    try:
        for index, entry in enumerate(manifest_docs):
            if max_docs is not None and index >= max_docs:
                break
            record = fetch_filing(session, entry)
            if record is None:
                doc_id = entry.get("document_id") or entry.get("receipt_no") or f"index-{index}"
                issue_counter["missing_document"] += 1
                results.append(
                    DocumentResult(
                        document_id=str(doc_id),
                        receipt_no=entry.get("receipt_no"),
                        chunk_count=0,
                        issues=[
                            ChunkIssue(
                                chunk_id=str(doc_id),
                                issue_type="missing_document",
                                details={},
                            )
                        ],
                    )
                )
                continue

            chunks = load_chunks(record.get("chunks"))
            document_issues: List[ChunkIssue] = []
            for chunk in chunks:
                chunk_issues = verify_chunk(chunk)
                document_issues.extend(chunk_issues)
                for issue in chunk_issues:
                    issue_counter[issue.issue_type] += 1

            results.append(
                DocumentResult(
                    document_id=str(record.get("id")),
                    receipt_no=record.get("receipt_no"),
                    chunk_count=len(chunks),
                    issues=document_issues,
                )
            )
    finally:
        session.close()

    return results, issue_counter


def build_report(
    manifest_path: Path,
    manifest_data: Dict[str, Any],
    results: Sequence[DocumentResult],
    issue_counter: Counter,
) -> Dict[str, Any]:
    total_docs = len(manifest_data.get("documents", []))
    evaluated_docs = len(results)
    chunk_total = sum(result.chunk_count for result in results)
    generated_at = datetime.now(timezone.utc).isoformat()

    serialized_results: List[Dict[str, Any]] = []
    for result in results:
        serialized_results.append(
            {
                "document_id": result.document_id,
                "receipt_no": result.receipt_no,
                "chunk_count": result.chunk_count,
                "issue_count": len(result.issues),
                "issues": [
                    {
                        "chunk_id": issue.chunk_id,
                        "type": issue.issue_type,
                        "details": issue.details,
                    }
                    for issue in result.issues[:50]
                ],
            }
        )

    return {
        "generated_at": generated_at,
        "manifest_path": str(manifest_path),
        "documents_in_manifest": total_docs,
        "documents_evaluated": evaluated_docs,
        "chunks_evaluated": chunk_total,
        "issue_counts": dict(issue_counter),
        "documents": serialized_results,
    }


def write_markdown(report: Dict[str, Any], path: Path) -> None:
    lines: List[str] = []
    lines.append(f"# Sentence Hash / Offset QA 보고서")
    lines.append("")
    lines.append(f"- 생성 시각: {report['generated_at']}")
    lines.append(f"- 매니페스트: `{report['manifest_path']}`")
    lines.append(f"- 평가 문서: {report['documents_evaluated']} / {report['documents_in_manifest']}")
    lines.append(f"- 평가 chunk 총계: {report['chunks_evaluated']}")
    lines.append("")
    lines.append("## 이슈 요약")
    if report["issue_counts"]:
        lines.append("| 이슈 유형 | 건수 |")
        lines.append("| --- | ---: |")
        for issue, count in sorted(report["issue_counts"].items(), key=lambda item: item[1], reverse=True):
            lines.append(f"| {issue} | {count} |")
    else:
        lines.append("- 발견된 이슈가 없습니다.")

    lines.append("")
    lines.append("## 문서별 세부내역 (상위 10건)")
    significant_docs = [
        doc for doc in report["documents"] if doc.get("issue_count", 0) > 0
    ]
    significant_docs = sorted(significant_docs, key=lambda doc: doc["issue_count"], reverse=True)[:10]

    if not significant_docs:
        lines.append("- 모든 문서가 통과했습니다.")
    else:
        for doc in significant_docs:
            lines.append(f"### Document {doc['document_id']} (issues: {doc['issue_count']})")
            if doc.get("receipt_no"):
                lines.append(f"- Receipt No: {doc['receipt_no']}")
            lines.append(f"- Chunk 수: {doc['chunk_count']}")
            lines.append("")
            lines.append("| Chunk ID | Issue | Details |")
            lines.append("| --- | --- | --- |")
            for issue in doc["issues"][:10]:
                details_json = json.dumps(issue.get("details") or {}, ensure_ascii=False)
                lines.append(f"| `{issue['chunk_id']}` | {issue['type']} | `{details_json}` |")
            lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sentence hash/offset QA 검증 스크립트")
    parser.add_argument("--manifest", type=Path, required=True, help="샘플 매니페스트 JSON 경로")
    parser.add_argument("--max-docs", type=int, default=None, help="검증할 최대 문서 수 (미지정 시 전체)")
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="JSON 리포트 출력 경로 (기본: reports/qa/verification_<timestamp>.json)",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=None,
        help="Markdown 리포트 출력 경로 (기본: reports/qa/verification_<timestamp>.md)",
    )
    parser.add_argument(
        "--fail-on-issues",
        action="store_true",
        help="이슈가 하나라도 발견되면 종료 코드 1 반환",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    manifest_path = args.manifest
    if not manifest_path.is_file():
        raise FileNotFoundError(f"매니페스트 파일을 찾을 수 없습니다: {manifest_path}")

    manifest = load_manifest(manifest_path)
    results, issue_counter = evaluate_documents(manifest["documents"], max_docs=args.max_docs)
    report = build_report(manifest_path, manifest, results, issue_counter)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    output_json = args.output_json or DEFAULT_REPORT_DIR / f"verification_{timestamp}.json"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("JSON 리포트를 %s에 저장했습니다.", output_json)

    if args.output_md or True:
        output_md = args.output_md or DEFAULT_REPORT_DIR / f"verification_{timestamp}.md"
        write_markdown(report, output_md)
        logger.info("Markdown 리포트를 %s에 저장했습니다.", output_md)

    issue_total = sum(issue_counter.values())
    logger.info("검증 완료: 문서 %d건, chunk %d건, 이슈 %d건.", report["documents_evaluated"], report["chunks_evaluated"], issue_total)

    if args.fail_on_issues and issue_total > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
