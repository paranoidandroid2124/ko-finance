from datetime import date

import pytest

from services import daily_brief_service as svc


def _mock_count_filings(session, *, start, end):
    return {"count": 5, "unique_companies": 3, "top_companies": ["기업A", "기업B", "기업C"]}


def _mock_count_news(session, *, start, end):
    return 12


def _mock_summarize_news(session, *, start, end):
    return {
        "count": 12,
        "positive": 6,
        "neutral": 4,
        "negative": 2,
        "avg_sentiment": 0.21,
        "top_topics": ["ESG", "투자 유치", "신제품"],
        "top_topics_detail": [
            {"topic": "ESG", "count": 4, "weight": 0.33},
            {"topic": "투자 유치", "count": 3, "weight": 0.25},
        ],
        "top_tickers": ["0001", "0002"],
        "top_positive_tickers": ["0001", "0003"],
        "top_sources": ["Yonhap", "Hankyung"],
        "filtered_count": 10,
        "raw_count": 12,
    }


def _mock_summarize_alerts(session, *, start, end):
    return {
        "count": 7,
        "top_channels": ["slack", "email"],
        "channel_counts": {"slack": 4, "email": 3},
        "status": {"delivered": 6, "failed": 1},
        "event_types": {"filing": 5, "news": 2},
        "top_tickers": ["0001", "0002"],
        "watchlist": {"count": 3, "tickers": ["0001", "0002"], "rules": ["Watch A"]},
        "news": {"count": 2, "sources": ["Yonhap"], "tickers": ["0002"]},
        "filing": {"count": 5, "categories": ["정정", "신규"]},
    }


def _mock_collect_evidence(session, *, start, end, limit, fallback_date, fallback_headline):
    return [
        {
            "source": "TestSource",
            "date": fallback_date.isoformat(),
            "title": "테스트 근거",
            "body": "테스트 본문",
            "trace_id": "trace-1",
            "url": "https://example.com",
        }
    ]


def _mock_rag_summary(records):
    return {
        "totalRuns": 4,
        "completed": 4,
        "failed": 0,
        "slaTargetMs": 30 * 60 * 1000,
        "p50DurationMs": 24 * 60 * 1000,
        "p95DurationMs": 32 * 60 * 1000,
        "slaBreaches": 0,
        "slaMet": 4,
        "latestTraceUrls": ["https://trace.example.com/abc"],
    }


@pytest.fixture(autouse=True)
def patch_daily_brief_helpers(monkeypatch):
    monkeypatch.setattr(svc, "_count_filings", _mock_count_filings)
    monkeypatch.setattr(svc, "_count_news", _mock_count_news)
    monkeypatch.setattr(svc, "_summarize_news", _mock_summarize_news)
    monkeypatch.setattr(svc, "_summarize_alerts", _mock_summarize_alerts)
    monkeypatch.setattr(svc, "_collect_evidence", _mock_collect_evidence)
    monkeypatch.setattr(svc.admin_rag_service, "list_reindex_history", lambda limit=80: [{"id": 1}])
    monkeypatch.setattr(svc.admin_rag_service, "summarize_reindex_history", _mock_rag_summary)


def test_build_daily_brief_payload_structure():
    payload = svc.build_daily_brief_payload(reference_date=date(2025, 1, 2), session=object(), use_llm=False)
    assert payload["report"]["date"] == "2025-01-02"
    assert payload["signals"], "signals should not be empty"
    assert any(signal["label"] == "Watchlist alerts" for signal in payload["signals"])
    assert payload["evidence"], "evidence should contain at least one entry"
    assert payload["metrics"], "metrics should be generated from RAG summary"
    assert payload["notes"][0].startswith("공시 수집"), "default notes should include filing insight"
    assert any("워치리스트" in alert["title"] for alert in payload["alerts"])
    assert any("워치리스트" in note for note in payload["notes"])
    assert payload["links"]["trace_url"] == "https://trace.example.com/abc"


def test_build_daily_brief_payload_with_llm(monkeypatch):
    monkeypatch.setattr(
        svc.llm_service,
        "generate_daily_brief_trend",
        lambda context: {"headline": "맞춤 헤드라인", "summary": "요약 문장", "model_used": "mock-model"},
    )
    payload = svc.build_daily_brief_payload(reference_date=date(2025, 1, 3), session=object(), use_llm=True)
    assert payload["report"]["headline"] == "맞춤 헤드라인"
    assert payload["notes"][0] == "요약 문장"
