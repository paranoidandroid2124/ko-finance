"""Toss Payments sandbox helper."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from core.env import env_str

logger = logging.getLogger(__name__)

DEFAULT_TOSS_API_BASE_URL = "https://api.tosspayments.com"


class TossPaymentsError(RuntimeError):
    """Raised when Toss Payments returns an error response."""

    def __init__(self, status_code: int, message: str, *, payload: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


def _basic_auth_header(secret_key: str) -> str:
    token = base64.b64encode(f"{secret_key}:".encode("utf-8")).decode("utf-8")
    return f"Basic {token}"


@dataclass(slots=True)
class TossPaymentsClient:
    """HTTP client wrapper for Toss Payments API."""

    client_key: str
    secret_key: str
    base_url: str = DEFAULT_TOSS_API_BASE_URL

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Dict[str, Any]] = None,
        timeout: float = 10.0,
    ) -> Dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {
            "Authorization": _basic_auth_header(self.secret_key),
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(method, url, headers=headers, json=json)
        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = {"body": response.text}
            message = payload.get("message") or payload.get("error") or "Toss Payments 요청이 실패했습니다."
            logger.warning("Toss Payments API error %s: %s", response.status_code, payload)
            raise TossPaymentsError(response.status_code, message, payload=payload)
        return response.json()

    async def create_payment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a payment using the Toss Payments direct API."""
        logger.info("Creating Toss Payments payment with orderId=%s", payload.get("orderId"))
        return await self._request("POST", "/v1/payments", json=payload)

    async def confirm_payment(self, payment_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Confirm a payment using the paymentKey returned from the widget."""
        logger.info("Confirming Toss Payments payment paymentKey=%s", payment_key)
        return await self._request("POST", "/v1/payments/confirm", json=dict(paymentKey=payment_key, **payload))


def get_toss_payments_client() -> TossPaymentsClient:
    client_key = env_str("TOSS_PAYMENTS_CLIENT_KEY")
    secret_key = env_str("TOSS_PAYMENTS_SECRET_KEY")
    if not client_key or not secret_key:
        raise RuntimeError("Toss Payments API 키가 설정되어 있지 않습니다. 환경변수를 확인해주세요.")
    base_url = env_str("TOSS_PAYMENTS_BASE_URL", DEFAULT_TOSS_API_BASE_URL) or DEFAULT_TOSS_API_BASE_URL
    return TossPaymentsClient(client_key=client_key, secret_key=secret_key, base_url=base_url)


def get_toss_public_config() -> dict[str, Optional[str]]:
    """Expose client-safe configuration values for the Toss Payments widget."""
    client_key = env_str("TOSS_PAYMENTS_CLIENT_KEY")
    if not client_key:
        raise RuntimeError("Toss Payments client key가 설정되어 있지 않습니다.")
    return {
        "clientKey": client_key,
        "successUrl": env_str("TOSS_PAYMENTS_SUCCESS_URL"),
        "failUrl": env_str("TOSS_PAYMENTS_FAIL_URL"),
    }


def get_toss_webhook_secret() -> str:
    secret = env_str("TOSS_PAYMENTS_WEBHOOK_SECRET")
    if not secret:
        raise RuntimeError("Toss Payments 웹훅 보안 키가 설정되지 않았습니다. 환경변수를 확인해 주세요.")
    return secret


def verify_toss_webhook_signature(
    *,
    payload: bytes,
    transmission_time: str,
    signature_header: str,
    secret: Optional[str] = None,
) -> bool:
    """Validate the Toss webhook signature header using the configured secret."""
    if not payload or not transmission_time or not signature_header:
        return False

    secret_key = secret or get_toss_webhook_secret()
    try:
        message = f"{payload.decode('utf-8')}:{transmission_time}"
    except UnicodeDecodeError:
        logger.warning("Toss webhook payload 디코딩에 실패했습니다.")
        return False

    digest = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()

    for part in signature_header.split(","):
        candidate = part.strip()
        if not candidate.startswith("v1:"):
            continue
        encoded = candidate[3:]
        try:
            decoded = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            logger.debug("잘못된 Toss webhook signature 조각이 감지되었습니다.")
            continue
        if hmac.compare_digest(digest, decoded):
            return True

    return False
