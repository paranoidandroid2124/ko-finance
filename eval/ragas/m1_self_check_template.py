"""
Ragas evaluation scaffold for M1 RAG answers.

Usage:
    python eval/ragas/m1_self_check_template.py --filing-id <UUID> --question "..."
"""

import argparse
import logging
from typing import List, Dict

from ragas.metrics import answer_relevancy, faithfulness
from ragas import evaluate

from services import vector_service
from llm import llm_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_ragas_evaluation(filing_id: str, question: str, top_k: int = 5):
    retrieval = vector_service.query_vector_store(
        query_text=question,
        filing_id=filing_id,
        top_k=top_k,
        max_filings=1,
        filters={},
    )
    context_chunks: List[Dict] = retrieval.chunks
    if not context_chunks:
        logger.error("No context returned from vector store.")
        return None

    answer_payload = llm_service.answer_with_rag(question, context_chunks)
    if answer_payload.get("error"):
        logger.error("RAG answer failed: %s", answer_payload["error"])
        return None

    logger.info("Answer warnings: %s", answer_payload.get("warnings"))
    logger.info("Answer citations: %s", answer_payload.get("citations"))

    dataset = [
        {
            "question": question,
            "answer": answer_payload["answer"],
            "contexts": [chunk.get("content", "") for chunk in context_chunks],
        }
    ]

    result = evaluate(dataset=dataset, metrics=[answer_relevancy, faithfulness])
    logger.info("Ragas Evaluation: %s", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--filing-id", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    run_ragas_evaluation(args.filing_id, args.question, args.top_k)
