# Evidence Fixtures

Synthetic RAG responses and evidence payloads used for Storybook, unit tests, and manual QA.

Guidelines:
- Keep schema aligned with `schemas/api/rag.py` Phase 2 fields (`urn_id`, `chunk_id`, `self_check`, `source_reliability`, etc.).
- Prefix filenames with the scenario (e.g., `highlight-success.json`, `anchor-mismatch.json`).
- These fixtures are not bundled in production; they are referenced only in tests or dev-only stories.
- Refresh the data whenever backend schema or reliability scoring logic changes.

## Available Scenarios

- `happy-path.json`: 완전 일치한 앵커와 `self_check.pass` 사례.
- `anchor-mismatch.json`: 앵커를 찾지 못해 하이라이트를 비활성화해야 하는 경고 흐름.
- `low-reliability.json`: `self_check.fail` + `source_reliability.low` 조합으로 배지/툴팁 검증용.
