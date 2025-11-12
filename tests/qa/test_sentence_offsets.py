from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from scripts.qa import verify_sentence_offsets as verifier


def test_build_report_handles_empty_manifest(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"documents": []}), encoding="utf-8")
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))

    report = verifier.build_report(
        manifest_path=manifest_path,
        manifest_data=manifest_data,
        results=[],
        issue_counter=verifier.Counter(),
    )
    assert report["documents_in_manifest"] == 0
    assert report["documents_evaluated"] == 0
    assert report["issue_counts"] == {}


def test_write_markdown_generates_summary(tmp_path: Path):
    report = {
        "generated_at": "2025-11-12T00:00:00Z",
        "manifest_path": "scripts/qa/samples/manifest.json",
        "documents_in_manifest": 1,
        "documents_evaluated": 1,
        "chunks_evaluated": 10,
        "issue_counts": {"hash_mismatch": 2, "missing_offsets": 1},
        "documents": [
            {
                "document_id": "doc-1",
                "receipt_no": "2024-00001",
                "chunk_count": 3,
                "issue_count": 2,
                "issues": [
                    {"chunk_id": "chunk-1", "type": "hash_mismatch", "details": {"expected": "abc", "recorded": "def"}},
                    {"chunk_id": "chunk-2", "type": "missing_offsets", "details": {}},
                ],
            }
        ],
    }

    output_path = tmp_path / "report.md"
    verifier.write_markdown(report, output_path)
    rendered = output_path.read_text(encoding="utf-8")
    assert "Sentence Hash / Offset QA" in rendered
    assert "| hash_mismatch | 2 |" in rendered
    assert "Document doc-1" in rendered


@mock.patch.object(verifier, "SessionLocal")
def test_evaluate_documents_handles_missing_document(session_factory):
    session = mock.Mock()
    session.execute.return_value.first.return_value = None
    session_factory.return_value = session

    results, counter = verifier.evaluate_documents([{"document_id": "00000000-0000-0000-0000-000000000000"}], max_docs=None)

    assert counter["missing_document"] == 1
    assert results[0].issues[0].issue_type == "missing_document"
