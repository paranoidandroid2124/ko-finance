"""Evaluate retrieval pipelines (dense, BM25, hybrid, hybrid+rerank)."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import sys

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from scripts._path import add_root

add_root()

from database import SessionLocal
from services import hybrid_search, vector_service


def _load_dataset(path: Path) -> List[Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON line: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError("Each dataset line must be a JSON object.")
            entries.append(payload)
    return entries


def _ranking_list(result: vector_service.VectorSearchResult) -> List[str]:
    ranking: List[str] = []
    for item in result.related_filings:
        doc_id = item.get("filing_id")
        if isinstance(doc_id, str):
            ranking.append(doc_id)
    return ranking


def _top_k_hit(ranking: Sequence[str], positives: Sequence[str]) -> Optional[int]:
    positive_set = {value for value in positives if value}
    if not positive_set:
        return None
    for idx, doc_id in enumerate(ranking, start=1):
        if doc_id in positive_set:
            return idx
    return None


def _ndcg_at_k(ranking: Sequence[str], positives: Sequence[str], k: int) -> float:
    if not positives:
        return 0.0
    gains = []
    relevant = set(positives)
    for idx, doc_id in enumerate(ranking[:k]):
        rel = 1.0 if doc_id in relevant else 0.0
        gains.append(rel / math.log2(idx + 2))
    dcg = sum(gains)
    ideal_len = min(k, len(relevant))
    ideal = sum(1.0 / math.log2(idx + 2) for idx in range(ideal_len))
    if ideal == 0:
        return 0.0
    return dcg / ideal


def _recall_at_k(ranking: Sequence[str], positives: Sequence[str], k: int) -> float:
    if not positives:
        return 0.0
    sample = set(ranking[:k])
    relevant = set(positives)
    return 1.0 if sample & relevant else 0.0


def _percentile(values: Sequence[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if percentile <= 0:
        return sorted_values[0]
    if percentile >= 100:
        return sorted_values[-1]
    rank = (percentile / 100.0) * (len(sorted_values) - 1)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_values[int(rank)]
    weight = rank - low
    return sorted_values[low] * (1 - weight) + sorted_values[high] * weight


def _evaluate_query(
    db,
    *,
    mode: str,
    query: str,
    filters: Dict[str, Any],
    top_k: int,
    candidate_k: int,
) -> vector_service.VectorSearchResult:
    if mode == "dense":
        return vector_service.query_vector_store(
            query_text=query,
            filing_id=None,
            top_k=top_k,
            max_filings=candidate_k,
            filters=filters,
        )
    if mode == "bm25":
        return hybrid_search.run_bm25_ranking(
            db,
            query,
            filters=filters,
            limit=candidate_k,
        )
    if mode == "hybrid":
        return hybrid_search.query_hybrid(
            db,
            query,
            filing_id=None,
            top_k=top_k,
            max_filings=candidate_k,
            filters=filters,
            use_reranker=False,
        )
    if mode in {"hybrid+vertex", "hybrid_rerank"}:
        return hybrid_search.query_hybrid(
            db,
            query,
            filing_id=None,
            top_k=top_k,
            max_filings=candidate_k,
            filters=filters,
            use_reranker=True,
        )
    raise ValueError(f"Unknown mode '{mode}'.")


def _load_baseline(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    parser = argparse.ArgumentParser(description="Hybrid retrieval evaluation.")
    parser.add_argument("--dataset", type=Path, required=True, help="Path to hybrid_v1.jsonl dataset.")
    parser.add_argument(
        "--mode",
        type=str,
        choices=["dense", "bm25", "hybrid", "hybrid+vertex", "hybrid_rerank"],
        default="hybrid+vertex",
    )
    parser.add_argument("--top-k", type=int, default=3, help="Chunks per filing / evaluation top-k.")
    parser.add_argument("--candidate-k", type=int, default=50, help="Number of filings to keep in ranking list.")
    parser.add_argument(
        "--baseline-report",
        type=Path,
        default=None,
        help="Optional previous report.json for delta comparison.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output path. Defaults to reports/hybrid/<timestamp>/report.json",
    )
    args = parser.parse_args()

    dataset = _load_dataset(args.dataset)
    if not dataset:
        raise SystemExit("Dataset is empty.")

    session = SessionLocal()
    latencies: List[float] = []
    top3_hits: List[int] = []
    mrr_scores: List[float] = []
    ndcg_scores: List[float] = []
    recall_scores: List[float] = []

    for entry in dataset:
        query = entry.get("query")
        if not isinstance(query, str) or not query.strip():
            continue
        positives = entry.get("positives") or []
        filters = entry.get("filters") or {}
        start = time.perf_counter()
        result = _evaluate_query(
            session,
            mode=args.mode,
            query=query,
            filters=filters,
            top_k=args.top_k,
            candidate_k=args.candidate_k,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        latencies.append(elapsed_ms)
        ranking = _ranking_list(result)
        hit_rank = _top_k_hit(ranking[: args.top_k], positives)
        top3_hits.append(1 if hit_rank is not None and hit_rank <= 3 else 0)
        if hit_rank is not None and hit_rank <= 10:
            mrr_scores.append(1.0 / hit_rank)
        else:
            mrr_scores.append(0.0)
        ndcg_scores.append(_ndcg_at_k(ranking, positives, 5))
        recall_scores.append(_recall_at_k(ranking, positives, 50))

    session.close()

    metrics = {
        "top3_accuracy": sum(top3_hits) / len(top3_hits),
        "mrr@10": sum(mrr_scores) / len(mrr_scores),
        "ndcg@5": sum(ndcg_scores) / len(ndcg_scores),
        "recall@50": sum(recall_scores) / len(recall_scores),
    }

    latency_stats = {
        "avg_ms": statistics.mean(latencies) if latencies else 0.0,
        "p50_ms": _percentile(latencies, 50),
        "p95_ms": _percentile(latencies, 95),
    }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(args.dataset),
        "mode": args.mode,
        "top_k": args.top_k,
        "candidate_k": args.candidate_k,
        "total_queries": len(dataset),
        "metrics": metrics,
        "latency_ms": latency_stats,
    }

    baseline = _load_baseline(args.baseline_report)
    if baseline and isinstance(baseline, dict):
        baseline_metrics = baseline.get("metrics") or {}
        comparison = {}
        for key, value in metrics.items():
            baseline_value = baseline_metrics.get(key)
            if isinstance(baseline_value, (int, float)):
                comparison[key] = value - baseline_value
        report["baseline_comparison"] = {
            "baseline_path": str(args.baseline_report),
            "delta": comparison,
        }

    output_path = args.output
    if output_path is None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output_path = Path("reports") / "hybrid" / timestamp / "report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved report to {output_path}")


if __name__ == "__main__":
    main()
