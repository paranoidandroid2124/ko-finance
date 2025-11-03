"""Tests for notification delivery helpers."""

from __future__ import annotations

from typing import Any, Dict, List

import httpx
import pytest

from services import notification_service


def test_slack_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: List[Dict[str, Any]] = []

    def fake_post(url: str, payload: Dict[str, Any], **kwargs: Any) -> notification_service.NotificationResult:
        captured.append(
            {
                "url": url,
                "payload": payload,
                "kwargs": kwargs,
            }
        )
        delivered = kwargs.get("success_count", 1)
        return notification_service.NotificationResult(
            status="delivered",
            delivered=delivered,
            metadata=kwargs.get("result_metadata"),
        )

    monkeypatch.setattr(notification_service, "_post_with_backoff", fake_post)

    blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "*친근한 안내*"}}]
    result = notification_service.dispatch_notification(
        channel="slack",
        message="테스트 알림",
        targets=["https://hooks.slack.com/services/demo"],
        metadata={"blocks": blocks, "attachments": [{"title": "Langfuse 경보"}]},
        template=None,
    )

    assert result.status == "delivered"
    assert result.delivered == 1
    assert len(captured) == 1
    dispatch_args = captured[0]
    assert dispatch_args["url"] == "https://hooks.slack.com/services/demo"
    assert dispatch_args["payload"]["text"] == "테스트 알림"
    assert dispatch_args["payload"]["blocks"] == blocks
    assert dispatch_args["kwargs"]["result_metadata"] == {"webhook": "https://hooks.slack.com/services/demo"}


def test_email_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notification_service, "ALERT_EMAIL_PROVIDER", "sendgrid")
    monkeypatch.setattr(notification_service, "ALERT_EMAIL_FROM", "alerts@kfinance.ai")
    monkeypatch.setattr(notification_service, "SENDGRID_API_KEY", "sg_test")

    captured: Dict[str, Any] = {}

    def fake_post(url: str, payload: Dict[str, Any], **kwargs: Any) -> notification_service.NotificationResult:
        captured["url"] = url
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        delivered = kwargs.get("success_count", 1)
        return notification_service.NotificationResult(
            status="delivered",
            delivered=delivered,
            metadata=kwargs.get("result_metadata"),
        )

    monkeypatch.setattr(notification_service, "_post_with_backoff", fake_post)

    metadata = {"subject": "따뜻한 알림", "html_template": "<p>{message}</p>"}
    result = notification_service.dispatch_notification(
        channel="email",
        message="테스트 알림",
        targets=["hello@kfinance.ai"],
        metadata=metadata,
        template=None,
    )

    assert result.status == "delivered"
    assert result.delivered == 1
    assert captured["url"] == "https://api.sendgrid.com/v3/mail/send"

    payload = captured["payload"]
    assert payload["personalizations"][0]["to"][0]["email"] == "hello@kfinance.ai"
    assert payload["from"]["email"] == "alerts@kfinance.ai"
    assert payload["content"][0]["value"] == "테스트 알림"
    assert payload["content"][1]["value"] == "<p>테스트 알림</p>"

    headers = captured["kwargs"]["headers"]
    assert headers["Authorization"] == "Bearer sg_test"
    assert captured["kwargs"]["result_metadata"] == {"recipients": ["hello@kfinance.ai"]}


def test_backoff_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    call_log: List[Dict[str, Any]] = []

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

    class DummyClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.url = kwargs.get("url")

        def __enter__(self) -> "DummyClient":
            return self

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            return None

        def post(self, url: str, json: Dict[str, Any], headers: Dict[str, Any] | None = None) -> DummyResponse:
            call_log.append({"url": url, "json": json, "headers": headers})
            if len(call_log) == 1:
                raise httpx.RequestError("boom", request=httpx.Request("POST", url))
            return DummyResponse()

    monkeypatch.setattr(notification_service.httpx, "Client", DummyClient)
    monkeypatch.setattr(notification_service.time, "sleep", lambda _: None)

    result = notification_service._post_with_backoff(
        "https://example.com/webhook",
        {"message": "테스트 알림"},
        max_attempts=2,
        success_count=1,
        result_metadata={"webhook": "https://example.com/webhook"},
    )

    assert result.status == "delivered"
    assert result.delivered == 1
    assert len(call_log) == 2
