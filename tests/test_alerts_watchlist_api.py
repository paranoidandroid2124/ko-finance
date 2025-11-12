from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from database import get_db
from services import watchlist_service
from web.routers import alerts as alerts_router
from services.plan_service import PlanContext, PlanQuota
from web.deps import get_plan_context


@pytest.fixture()
def watchlist_api_client(monkeypatch: pytest.MonkeyPatch):
    app = FastAPI()
    app.include_router(alerts_router.router, prefix="/api/v1")

    def override_db():
        yield None

    app.dependency_overrides[get_db] = override_db

    plan_context = PlanContext(
        tier="pro",
        base_tier="pro",
        expires_at=None,
        entitlements=frozenset({"search.alerts"}),
        quota=PlanQuota(
            chat_requests_per_day=None,
            rag_top_k=None,
            self_check_enabled=True,
            peer_export_row_limit=None,
        ),
        memory_watchlist_enabled=True,
    )

    app.dependency_overrides[get_plan_context] = lambda: plan_context

    sample_payload = {
        "generatedAt": "2025-01-01T12:00:00+00:00",
        "windowMinutes": 60,
        "window": {"start": "2025-01-01T11:00:00+00:00", "end": "2025-01-01T12:00:00+00:00"},
        "summary": {
            "totalDeliveries": 2,
            "totalEvents": 2,
            "uniqueTickers": 2,
            "topTickers": ["0001", "0002"],
            "topChannels": {"slack": 1, "email": 1},
            "topRules": ["Watchlist Radar"],
            "failedDeliveries": 0,
            "channelFailures": {},
            "windowStart": "2025-01-01T11:00:00+00:00",
            "windowEnd": "2025-01-01T12:00:00+00:00",
        },
        "items": [
            {
                "deliveryId": "1",
                "ruleId": "1",
                "ruleName": "Watchlist Radar",
                "channel": "slack",
                "eventType": "news",
                "ruleTags": [],
                "ruleTickers": ["0001"],
                "deliveryStatus": "delivered",
                "deliveryError": None,
                "ruleErrorCount": 0,
                "ticker": "0001",
                "company": "ê¸°ì—…A",
                "category": "ê³µì‹œ",
                "source": "DART",
                "headline": "í…ŒìŠ¤íŠ¸ í—¤ë“œë¼ì¸",
                "summary": "í…ŒìŠ¤íŠ¸ í—¤ë“œë¼ì¸",
                "sentiment": 0.2,
                "message": "ì•Œë¦¼",
                "deliveredAt": "2025-01-01T11:30:00+00:00",
                "eventTime": "2025-01-01T11:20:00+00:00",
                "url": "https://example.com/event",
            }
        ],
    }

    def fake_collect(db, window_minutes, limit, owner_filters=None, **kwargs):
        return sample_payload

    monkeypatch.setattr(
        watchlist_service,
        "collect_watchlist_alerts",
        fake_collect,
    )

    client = TestClient(app)
    try:
        yield client, sample_payload
    finally:
        client.close()


def test_watchlist_radar_endpoint(watchlist_api_client):
    client, sample = watchlist_api_client
    response = client.get("/api/v1/alerts/watchlist/radar?window_minutes=120&limit=5")
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["totalDeliveries"] == sample["summary"]["totalDeliveries"]
    assert payload["items"][0]["ticker"] == "0001"

def test_watchlist_dispatch_endpoint(watchlist_api_client, monkeypatch: pytest.MonkeyPatch):
    client, sample = watchlist_api_client

    def fake_dispatch(db, window_minutes, limit, slack_targets, email_targets, owner_filters=None, **kwargs):
        return {
            "payload": sample,
            "results": [
                {"channel": "slack", "status": "delivered", "delivered": len(slack_targets or []), "failed": 0, "error": None}
            ],
        }

    monkeypatch.setattr(watchlist_service, "dispatch_watchlist_digest", fake_dispatch)

    response = client.post(
        "/api/v1/alerts/watchlist/dispatch",
        json={"slackTargets": ["https://hooks.slack.com/services/demo"], "windowMinutes": 120},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["results"][0]["channel"] == "slack"
    assert data["results"][0]["status"] == "delivered"


def test_watchlist_rule_detail_endpoint(watchlist_api_client, monkeypatch: pytest.MonkeyPatch):
    client, _ = watchlist_api_client

    detail_payload = {
        "rule": {
            "id": "11111111-1111-1111-1111-111111111111",
            "name": "워치리스트 룰",
            "description": "테스트 룰",
            "status": "active",
            "evaluationIntervalMinutes": 5,
            "windowMinutes": 60,
            "cooldownMinutes": 30,
            "maxTriggersPerDay": 20,
            "condition": {
                "type": "news",
                "tickers": ["0001"],
                "categories": ["공시"],
                "sectors": [],
                "minSentiment": -0.2,
            },
            "channels": [
                {
                    "type": "slack",
                    "label": "#alerts",
                    "target": "#alerts",
                    "targets": ["#alerts"],
                    "metadata": {},
                }
            ],
            "extras": {"category": "watch"},
            "lastTriggeredAt": "2025-01-01T11:45:00+00:00",
            "lastEvaluatedAt": "2025-01-01T11:50:00+00:00",
            "errorCount": 1,
        },
        "recentDeliveries": [
            {
                "deliveryId": "deliv-1",
                "channel": "slack",
                "status": "failed",
                "deliveredAt": "2025-01-01T11:30:00+00:00",
                "error": "channel_not_found",
                "eventCount": 1,
                "events": [
                    {
                        "ticker": "0001",
                        "headline": "테스트 실패",
                        "summary": "테스트 실패",
                        "sentiment": -0.5,
                        "category": "공시",
                        "url": "https://example.com/fail",
                        "eventTime": "2025-01-01T11:25:00+00:00",
                    }
                ],
            }
        ],
        "totalDeliveries": 3,
        "failedDeliveries": 1,
    }

    monkeypatch.setattr(
        watchlist_service,
        "collect_watchlist_rule_detail",
        lambda db, rule_id, owner_filters=None, recent_limit=5: detail_payload,
    )

    response = client.get(
        "/api/v1/alerts/watchlist/rules/11111111-1111-1111-1111-111111111111/detail?recent_limit=3"
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["rule"]["id"] == detail_payload["rule"]["id"]
    assert payload["totalDeliveries"] == detail_payload["totalDeliveries"]
    assert payload["recentDeliveries"][0]["eventCount"] == 1

