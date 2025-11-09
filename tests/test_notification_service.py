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


def test_email_dispatch_smtp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notification_service, "ALERT_EMAIL_PROVIDER", "nhn_smtp")
    monkeypatch.setattr(notification_service, "ALERT_EMAIL_FROM", "alerts@kfinance.ai")
    monkeypatch.setattr(notification_service, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(notification_service, "SMTP_PORT", 587)
    monkeypatch.setattr(notification_service, "SMTP_USERNAME", "smtp-user")
    monkeypatch.setattr(notification_service, "SMTP_PASSWORD", "smtp-pass")
    monkeypatch.setattr(notification_service, "SMTP_USE_TLS", True)

    captured: Dict[str, Any] = {}

    class DummySMTP:
        def __init__(self, host: str, port: int) -> None:
            captured["host"] = host
            captured["port"] = port
            self.sent: List[Dict[str, Any]] = []

        def __enter__(self) -> "DummySMTP":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def starttls(self) -> None:
            captured["starttls"] = True

        def login(self, username: str, password: str) -> None:
            captured["login"] = (username, password)

        def send_message(self, msg) -> None:
            captured["message"] = msg

    monkeypatch.setattr(notification_service.smtplib, "SMTP", DummySMTP)

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
    assert captured["host"] == "smtp.test"
    assert captured["port"] == 587
    assert captured["starttls"] is True
    assert captured["login"] == ("smtp-user", "smtp-pass")

    msg = captured["message"]
    assert msg["To"] == "hello@kfinance.ai"
    assert msg["From"] == "alerts@kfinance.ai"


def test_email_dispatch_nhn_rest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(notification_service, "ALERT_EMAIL_PROVIDER", "nhn_rest")
    monkeypatch.setattr(notification_service, "NHN_APP_KEY", "app-key")
    monkeypatch.setattr(notification_service, "NHN_SECRET_KEY", "secret")
    monkeypatch.setattr(notification_service, "NHN_EMAIL_BASE_URL", "https://email.api.nhncloudservice.com")
    monkeypatch.setattr(notification_service, "NHN_SENDER_ADDRESS", "alerts@kfinance.ai")
    monkeypatch.setattr(notification_service, "NHN_SENDER_NAME", "K-Finance QA")

    captured: Dict[str, Any] = {}

    def fake_post(url: str, payload: Dict[str, Any], **kwargs: Any) -> notification_service.NotificationResult:
        captured["url"] = url
        captured["payload"] = payload
        captured["kwargs"] = kwargs
        return notification_service.NotificationResult(status="delivered", delivered=kwargs.get("success_count", 1))

    monkeypatch.setattr(notification_service, "_post_with_backoff", fake_post)

    metadata = {"subject": "테스트", "html_template": "<p>{message}</p>"}
    result = notification_service.dispatch_notification(
        channel="email",
        message="본문",
        targets=["hello@kfinance.ai"],
        metadata=metadata,
        template=None,
    )

    assert result.status == "delivered"
    assert captured["url"].endswith("/email/v2.1/appKeys/app-key/sender/mail")
    payload = captured["payload"]
    assert payload["senderAddress"] == "alerts@kfinance.ai"
    assert payload["senderName"] == "K-Finance QA"
    assert payload["receiverList"][0]["receiveMailAddr"] == "hello@kfinance.ai"
    headers = captured["kwargs"]["headers"]
    assert headers["X-Secret-Key"] == "secret"


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
