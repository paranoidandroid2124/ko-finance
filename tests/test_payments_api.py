import base64
import hashlib
import hmac
import json
from pathlib import Path
from typing import Any, Dict, Iterator, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from web.routers.payments import router as payments_router


@pytest.fixture()
def payments_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Configure Toss Payments env vars and return a FastAPI test client."""
    monkeypatch.setenv("TOSS_PAYMENTS_CLIENT_KEY", "test_ck_demo")
    monkeypatch.setenv("TOSS_PAYMENTS_SECRET_KEY", "test_sk_demo")
    monkeypatch.delenv("TOSS_PAYMENTS_SUCCESS_URL", raising=False)
    monkeypatch.delenv("TOSS_PAYMENTS_FAIL_URL", raising=False)

    app = FastAPI()
    app.include_router(payments_router, prefix="/api/v1")
    client = TestClient(app)
    try:
        yield client
    finally:
        client.close()


@pytest.fixture()
def payments_webhook_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[Tuple[TestClient, Path]]:
    """Configure env vars and persisted plan settings for webhook handling tests."""
    plan_settings_path = tmp_path / "plan_settings.json"
    plan_settings_path.write_text(
        json.dumps(
            {
                "planTier": "pro",
                "expiresAt": None,
                "entitlements": ["search.compare", "search.alerts", "evidence.inline_pdf"],
                "quota": {
                    "chatRequestsPerDay": 500,
                    "ragTopK": 6,
                    "selfCheckEnabled": True,
                    "peerExportRowLimit": 100,
                },
                "updatedAt": "2025-10-30T00:00:00+00:00",
                "updatedBy": "qa@kfinance.ai",
                "changeNote": "initial state for tests",
                "checkoutRequested": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("PLAN_SETTINGS_FILE", str(plan_settings_path))
    monkeypatch.setenv("TOSS_PAYMENTS_WEBHOOK_SECRET", "demo_webhook_secret")
    monkeypatch.setenv("TOSS_PAYMENTS_CLIENT_KEY", "test_ck_demo")
    monkeypatch.setenv("TOSS_PAYMENTS_SECRET_KEY", "test_sk_demo")
    monkeypatch.delenv("TOSS_PAYMENTS_SUCCESS_URL", raising=False)
    monkeypatch.delenv("TOSS_PAYMENTS_FAIL_URL", raising=False)

    app = FastAPI()
    app.include_router(payments_router, prefix="/api/v1")
    client = TestClient(app)
    try:
        yield client, plan_settings_path
    finally:
        client.close()


def test_read_toss_config(payments_client: TestClient):
    response = payments_client.get("/api/v1/payments/toss/config")
    assert response.status_code == 200
    payload = response.json()
    assert payload["clientKey"] == "test_ck_demo"
    assert payload["successUrl"] is None
    assert payload["failUrl"] is None


async def _mock_confirm_payment(_self, payment_key: str, payload: Dict[str, Any]):
    return {
        "paymentKey": payment_key,
        "orderId": payload["orderId"],
        "approvedAt": "2025-10-30T09:30:00+09:00",
        "amount": payload["amount"],
        "status": "DONE",
    }


def test_confirm_toss_payment(payments_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    class DummyClient:
        async def confirm_payment(self, payment_key: str, payload: Dict[str, Any]):
            return await _mock_confirm_payment(self, payment_key, payload)

    from web.routers import payments as payments_router

    monkeypatch.setattr(payments_router, "get_toss_payments_client", lambda: DummyClient())

    response = payments_client.post(
        "/api/v1/payments/toss/confirm",
        json={"paymentKey": "pay_123", "orderId": "order_abc", "amount": 1000},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["paymentKey"] == "pay_123"
    assert payload["orderId"] == "order_abc"
    assert payload["approvedAt"] == "2025-10-30T09:30:00+09:00"


def test_confirm_missing_config(payments_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from web.routers import payments as payments_router

    def _raise_config_error():
        raise RuntimeError("키가 아직 설정되지 않았습니다.")

    monkeypatch.setattr(payments_router, "get_toss_payments_client", _raise_config_error)
    response = payments_client.post(
        "/api/v1/payments/toss/confirm",
        json={"paymentKey": "pay_123", "orderId": "order_abc", "amount": 1000},
    )
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["code"] == "payments.config_missing"


def _build_webhook_headers(payload: Dict[str, Any], secret: str, transmission_time: str) -> Dict[str, str]:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{body}:{transmission_time}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature = base64.b64encode(digest).decode("ascii")
    return {
        "Content-Type": "application/json",
        "tosspayments-webhook-transmission-time": transmission_time,
        "tosspayments-webhook-signature": f"v1:{signature}",
    }, body


def test_toss_webhook_applies_plan_upgrade(payments_webhook_client: Tuple[TestClient, Path]):
    client, plan_path = payments_webhook_client
    payload = {
        "eventType": "PAYMENT_STATUS_CHANGED",
        "createdAt": "2025-10-30T09:30:00+09:00",
        "data": {
            "orderId": "kfinance-enterprise-12345",
            "paymentKey": "pay_12345",
            "status": "DONE",
        },
    }
    headers, body = _build_webhook_headers(payload, "demo_webhook_secret", "2024-09-05T12:19:21+09:00")

    response = client.post("/api/v1/payments/toss/webhook", data=body, headers=headers)
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"

    saved = json.loads(plan_path.read_text(encoding="utf-8"))
    assert saved["planTier"] == "enterprise"
    assert saved["checkoutRequested"] is False
    assert "timeline.full" in saved["entitlements"]
    assert saved["updatedBy"] == "toss-webhook"


def test_toss_webhook_rejects_invalid_signature(payments_webhook_client: Tuple[TestClient, Path]):
    client, plan_path = payments_webhook_client
    payload = {
        "eventType": "PAYMENT_STATUS_CHANGED",
        "createdAt": "2025-10-30T09:30:00+09:00",
        "data": {
            "orderId": "kfinance-enterprise-12345",
            "paymentKey": "pay_12345",
            "status": "DONE",
        },
    }
    headers, body = _build_webhook_headers(payload, "different_secret", "2024-09-05T12:19:21+09:00")

    response = client.post("/api/v1/payments/toss/webhook", data=body, headers=headers)
    assert response.status_code == 401
    saved = json.loads(plan_path.read_text(encoding="utf-8"))
    assert saved["checkoutRequested"] is True
    assert saved["planTier"] == "pro"


def test_toss_webhook_clears_checkout_on_cancel(payments_webhook_client: Tuple[TestClient, Path]):
    client, plan_path = payments_webhook_client
    payload = {
        "eventType": "PAYMENT_STATUS_CHANGED",
        "createdAt": "2025-10-30T09:30:00+09:00",
        "data": {
            "orderId": "kfinance-pro-67890",
            "paymentKey": "pay_67890",
            "status": "CANCELED",
        },
    }
    headers, body = _build_webhook_headers(payload, "demo_webhook_secret", "2024-09-05T12:19:21+09:00")

    response = client.post("/api/v1/payments/toss/webhook", data=body, headers=headers)
    assert response.status_code == 202

    saved = json.loads(plan_path.read_text(encoding="utf-8"))
    assert saved["planTier"] == "pro"
    assert saved["checkoutRequested"] is False
