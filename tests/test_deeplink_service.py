import pytest

from services import deeplink_service


@pytest.fixture(autouse=True)
def configure_deeplink(monkeypatch):
    monkeypatch.setattr(deeplink_service, "DEEPLINK_SECRET", "unit-test-secret", raising=False)
    monkeypatch.setattr(deeplink_service, "DEEPLINK_TTL_SECONDS", 120, raising=False)
    monkeypatch.setattr(deeplink_service, "DEEPLINK_VIEWER_BASE_URL", "/viewer", raising=False)
    yield


def test_issue_and_resolve_deeplink_token():
    assert deeplink_service.is_enabled()

    token = deeplink_service.issue_token(
        document_url="https://example.com/doc.pdf",
        page_number=3,
        char_start=10,
        char_end=42,
        sentence_hash="hash-123",
        chunk_id="chunk-1",
        document_id="filing-1",
        excerpt="Sample excerpt",
    )
    viewer_url = deeplink_service.build_viewer_url(token)
    assert viewer_url.endswith(token)

    payload = deeplink_service.resolve_token(token)
    assert payload["document_url"] == "https://example.com/doc.pdf"
    assert payload["page_number"] == 3
    assert payload["char_start"] == 10
    assert payload["char_end"] == 42
    assert payload["sentence_hash"] == "hash-123"
    assert payload["chunk_id"] == "chunk-1"
    assert payload["document_id"] == "filing-1"
    assert payload["excerpt"] == "Sample excerpt"
    assert "expires_at" in payload


def test_invalid_token_raises_error():
    with pytest.raises(deeplink_service.DeeplinkInvalidError):
        deeplink_service.resolve_token("not-a-real-token")
