## Hybrid Search Evaluation Datasets

- `hybrid_v1.jsonl` (not committed) should contain one JSON document per line with:
  ```json
  {
    "query": "질문 문자열",
    "positives": ["uuid-of-relevant-document"],
    "hard_negatives": ["uuid-of-confuser"],
    "filters": {"ticker": "005930.KS"}
  }
  ```
- Use `hybrid_v1.sample.jsonl` as a template when curating new questions. Actual production sets live outside the repository because they include proprietary filings/news identifiers.
