from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Optional, Sequence

import pytest

from models.alert import AlertDelivery, AlertRule
from services import watchlist_service, notification_service
from services.notification_service import NotificationResult


def _sample_rule(name: str = "Watchlist Radar") -> AlertRule:
    return AlertRule(
        id=uuid.uuid4(),
        plan_tier="pro",
        name=name,
        trigger={"type": "news", "tickers": ["0001"], "scope": "watchlist"},
        extras={"category": "watch"},
        channels=[],
    )


def _sample_delivery(
    rule: AlertRule,
    ticker: str,
    *,
    channel: str = "slack",
    status: str = "delivered",
    error_message: str | None = None,
) -> AlertDelivery:
    return AlertDelivery(
        id=uuid.uuid4(),
        alert_id=rule.id,
        channel=channel,
        status=status,
        message=f"{ticker} watchlist alert",
        context={
            "events": [
                {
                    "ticker": ticker,
                    "headline": f"{ticker} headline",
                    "source": "Yonhap",
                    "sentiment": 0.42,
                    "category": "ì •ì •",
                    "url": "https://example.com/event",
                    "published_at": datetime.now(timezone.utc).isoformat(),
                }
            ]
        },
        error_message=error_message,
        created_at=datetime.now(timezone.utc),
    )


class FakeRuleQuery:
    def __init__(self, rule: AlertRule):
        self.rule = rule

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.rule


class FakeDeliveryQuery:
    def __init__(self, deliveries: Sequence[AlertDelivery]):
        self._deliveries = list(deliveries)
        self._limit: Optional[int] = None

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, value: int):
        self._limit = value
        return self

    def all(self):
        if self._limit is None:
            return list(self._deliveries)
        return list(self._deliveries)[: self._limit]


class FakeStatusQuery:
    def __init__(self, deliveries: Sequence[AlertDelivery]):
        self._deliveries = list(deliveries)

    def filter(self, *args, **kwargs):
        return self

    def group_by(self, *args, **kwargs):
        counts = Counter(str(getattr(delivery, "status", "")).lower() for delivery in self._deliveries)

        class _Result:
            def __init__(self, data):
                self._data = data

            def all(self):
                return list(self._data.items())

        return _Result(counts)


class FakeSession:
    def __init__(self, rule: AlertRule, deliveries: Sequence[AlertDelivery]):
        self.rule = rule
        self.deliveries = list(deliveries)

    def query(self, *entities):
        first = entities[0]
        if first is AlertRule:
            return FakeRuleQuery(self.rule)
        if first is AlertDelivery:
            return FakeDeliveryQuery(self.deliveries)
        if first == AlertDelivery.status:
            return FakeStatusQuery(self.deliveries)
        raise NotImplementedError(f"Unsupported query entity: {first!r}")


def test_collect_watchlist_alerts_aggregates_summary() -> None:
    rule = _sample_rule()
    delivery_a = _sample_delivery(rule, "0001", channel="slack")
    delivery_b = _sample_delivery(rule, "0002", channel="email")

    payload = watchlist_service.collect_watchlist_alerts(
        db=SimpleNamespace(),  # unused because we provide override
        window_minutes=120,
        limit=10,
        _rows_override=[(delivery_a, rule), (delivery_b, rule)],
    )

    summary = payload["summary"]
    assert summary["totalDeliveries"] == 2
    assert summary["failedDeliveries"] == 0
    assert summary["totalEvents"] == 2
    assert summary["uniqueTickers"] == 2
    assert "0001" in summary["topTickers"]
    first_item = payload["items"][0]
    assert first_item["ruleName"] == rule.name
    assert first_item["deliveryStatus"] == "delivered"
    assert first_item["ruleErrorCount"] == 0


def test_collect_watchlist_alerts_filters_by_channel_and_event_type() -> None:
    news_rule = _sample_rule()
    filing_rule = _sample_rule(name="Filing Radar")
    filing_rule.trigger = {"type": "filing", "tickers": ["0003"], "scope": "watchlist"}
    filing_rule.extras = {"tags": ["FILING"], "category": "watch"}

    slack_delivery = _sample_delivery(news_rule, "0001", channel="slack")
    email_delivery = _sample_delivery(filing_rule, "0003", channel="email")

    payload = watchlist_service.collect_watchlist_alerts(
        db=SimpleNamespace(),
        window_minutes=240,
        limit=10,
        channels=["email"],
        event_types=["filing"],
        _rows_override=[(slack_delivery, news_rule), (email_delivery, filing_rule)],
    )

    assert payload["summary"]["totalDeliveries"] == 1
    assert payload["summary"]["failedDeliveries"] == 0
    assert payload["items"][0]["channel"] == "email"
    assert payload["items"][0]["eventType"] == "filing"
    assert payload["items"][0]["ruleTags"] == ["FILING"]
    assert payload["items"][0]["deliveryStatus"] == "delivered"


def test_collect_watchlist_alerts_filters_by_ticker_and_query() -> None:
    rule = _sample_rule()
    delivery_a = _sample_delivery(rule, "0001", channel="slack")
    delivery_b = _sample_delivery(rule, "0002", channel="slack")

    payload = watchlist_service.collect_watchlist_alerts(
        db=SimpleNamespace(),
        window_minutes=120,
        limit=10,
        tickers=["0002"],
        query="0002 headline",
        _rows_override=[(delivery_a, rule), (delivery_b, rule)],
    )

    assert payload["summary"]["totalDeliveries"] == 1
    assert len(payload["items"]) == 1
    assert payload["items"][0]["ticker"] == "0002"
    assert payload["items"][0]["deliveryStatus"] == "delivered"


def test_collect_watchlist_alerts_includes_failed_deliveries() -> None:
    rule = _sample_rule()
    failed_delivery = _sample_delivery(
        rule,
        "0004",
        channel="slack",
        status="failed",
        error_message="Channel not found",
    )

    payload = watchlist_service.collect_watchlist_alerts(
        db=SimpleNamespace(),
        window_minutes=60,
        limit=10,
        _rows_override=[(failed_delivery, rule)],
    )

    summary = payload["summary"]
    assert summary["totalDeliveries"] == 0
    assert summary["failedDeliveries"] == 1
    assert summary["channelFailures"]["slack"] == 1
    assert summary["topChannels"] == {}
    assert payload["items"][0]["deliveryStatus"] == "failed"
    assert payload["items"][0]["deliveryError"] == "Channel not found"


def test_collect_watchlist_rule_detail_returns_recent_logs() -> None:
    rule = _sample_rule()
    rule.channels = [
        {"type": "slack", "label": "#alerts", "target": "#alerts", "targets": ["#alerts"], "metadata": {}},
        {"type": "email", "target": "alerts@example.com", "targets": ["alerts@example.com"], "metadata": {}},
    ]
    rule.description = "테스트 룰"
    now = datetime.now(timezone.utc)
    rule.last_triggered_at = now
    rule.last_evaluated_at = now
    rule.error_count = 2

    failed_delivery = _sample_delivery(
        rule,
        "0004",
        channel="slack",
        status="failed",
        error_message="channel_not_found",
    )
    delivered = _sample_delivery(rule, "0001", channel="email", status="delivered")

    session = FakeSession(rule, [failed_delivery, delivered])

    detail = watchlist_service.collect_watchlist_rule_detail(
        session,
        rule_id=rule.id,
        owner_filters={},
        recent_limit=5,
    )

    assert detail["rule"]["id"] == str(rule.id)
    assert detail["totalDeliveries"] == 1
    assert detail["failedDeliveries"] == 1
    assert len(detail["recentDeliveries"]) == 2
    assert detail["recentDeliveries"][0]["eventCount"] == 1


