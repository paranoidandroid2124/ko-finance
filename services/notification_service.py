"""Notification channel adapters used by alert delivery."""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

ALERT_EMAIL_PROVIDER = (os.getenv("ALERT_EMAIL_PROVIDER") or "sendgrid").lower()
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

ALERT_SLACK_DEFAULT_WEBHOOK = os.getenv("ALERT_SLACK_WEBHOOK_URL")
ALERT_WEBHOOK_TIMEOUT = float(os.getenv("ALERT_REQUEST_TIMEOUT", "10"))
ALERT_WEBHOOK_RETRIES = int(os.getenv("ALERT_REQUEST_RETRIES", "3"))

PAGERDUTY_ROUTING_KEY = os.getenv("PAGERDUTY_ROUTING_KEY")


@dataclass
class NotificationResult:
    status: str
    error: Optional[str] = None
    delivered: int = 0
    failed: int = 0
    metadata: Optional[Dict[str, Any]] = None


def _unique_targets(primary: Optional[str], extra: Optional[Iterable[str]] = None) -> List[str]:
    """Return a de-duplicated list of delivery targets."""
    unique: List[str] = []
    sources: List[Iterable[str]] = []
    if primary:
        sources.append([primary])
    if extra:
        sources.append(extra)
    for source in sources:
        for item in source:
            if not isinstance(item, str):
                continue
            candidate = item.strip()
            if candidate and candidate not in unique:
                unique.append(candidate)
    return unique


def _format_template(value: Optional[str], context: Dict[str, Any]) -> Optional[str]:
    if not isinstance(value, str):
        return None
    try:
        return value.format(**context)
    except Exception as exc:  # pragma: no cover - template safety net
        logger.debug("Channel template rendering failed for value=%s context=%s: %s", value, context, exc)
        return value


def _render_channel_payload(
    message: str,
    metadata: Optional[Dict[str, Any]],
    template: Optional[str],
) -> Dict[str, Any]:
    context: Dict[str, Any] = dict(metadata or {})
    context.setdefault("message", message)
    subject = _format_template(
        context.get("subject_template") or context.get("subject"),
        context,
    )
    body_template = context.get("body_template") or context.get("body")
    body = _format_template(body_template, context) if body_template else None
    if not isinstance(body, str) or not body.strip():
        body = message
    if template == "markdown" and not body.startswith("```") and context.get("markdown"):
        body = context["markdown"]
    payload = {
        "body": body,
        "subject": subject,
        "blocks": context.get("blocks"),
        "context": context,
    }
    return payload


def _aggregate_results(results: Sequence[NotificationResult]) -> NotificationResult:
    if not results:
        return NotificationResult(status="failed", error="ë°œì†¡ ëŒ€ìƒì´ ì—†ìŠµë‹ˆë‹¤.", delivered=0, failed=0)
    delivered = sum(result.delivered for result in results)
    failed = sum(result.failed for result in results)
    errors = [result.error for result in results if result.error]
    if failed and delivered:
        status = "partial"
    elif failed:
        status = "failed"
    else:
        status = "delivered"
    error_message = "; ".join(errors) if errors else None
    return NotificationResult(status=status, error=error_message, delivered=delivered, failed=failed)


def send_telegram_alert(message: str, chat_id: Optional[str] = None) -> bool:
    """Send a message to the configured Telegram chat."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram BOT token is missing.")
        return False

    target_chat = chat_id or TELEGRAM_CHAT_ID
    if not target_chat:
        logger.warning("Telegram chat ID is missing.")
        return False

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": target_chat,
        "text": message,
        "parse_mode": "Markdown",
    }

    try:
        with httpx.Client(timeout=ALERT_WEBHOOK_TIMEOUT) as client:
            response = client.post(api_url, json=payload)
            response.raise_for_status()
        success = bool(response.json().get("ok"))
        if success:
            logger.info("Telegram alert sent successfully.")
        else:
            logger.error("Telegram API responded with an error: %s", response.json())
        return success
    except httpx.HTTPStatusError as exc:
        logger.error("Telegram alert failed with HTTP error: %s", exc.response.text)
        return False
    except Exception as exc:  # pragma: no cover - network failure best-effort
        logger.error("Telegram alert failed: %s", exc, exc_info=True)
        return False


def dispatch_notification(
    channel: str,
    message: str,
    target: Optional[str] = None,
    *,
    targets: Optional[Sequence[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    template: Optional[str] = None,
) -> NotificationResult:
    """Route alert delivery to the requested channel."""
    handler = CHANNEL_REGISTRY.get(channel.lower())
    if handler is None:
        logger.warning("Unsupported alert channel requested: %s", channel)
        return NotificationResult(status="failed", error=f"지원되지 않는 채널 {channel}")
    resolved_targets = _unique_targets(target, targets)
    rendered = _render_channel_payload(message, metadata, template)
    return handler(
        rendered["body"],
        resolved_targets[0] if resolved_targets else None,
        targets=resolved_targets,
        metadata=metadata or {},
        rendered=rendered,
    )


def _handle_telegram(
    message: str,
    target: Optional[str],
    *,
    targets: Sequence[str],
    metadata: Dict[str, Any],
    rendered: Dict[str, Any],
) -> NotificationResult:
    recipients = list(targets)
    meta_targets = metadata.get("chat_ids")
    if not recipients and isinstance(meta_targets, (list, tuple, set)):
        recipients = _unique_targets(None, meta_targets)
    if not recipients and TELEGRAM_CHAT_ID:
        recipients = [TELEGRAM_CHAT_ID]
    if not recipients:
        return NotificationResult(status="failed", error="텔레그램 대상(chat_id)이 필요합니다.")
    successes = 0
    for chat_id in recipients:
        if send_telegram_alert(message, chat_id=chat_id):
            successes += 1
    failures = len(recipients) - successes
    status = "delivered" if failures == 0 else ("partial" if successes else "failed")
    error = None if failures == 0 else "텔레그램 발송 실패"
    return NotificationResult(status=status, error=error, delivered=successes, failed=failures)


def _handle_email(
    message: str,
    target: Optional[str],
    *,
    targets: Sequence[str],
    metadata: Dict[str, Any],
    rendered: Dict[str, Any],
) -> NotificationResult:
    recipients = list(targets) or _unique_targets(target, None)
    if not recipients:
        return NotificationResult(status="failed", error="이메일 수신자(target)가 필요합니다.")

    if ALERT_EMAIL_PROVIDER != "sendgrid":
        logger.warning("Email provider %s is not supported; skipping send.", ALERT_EMAIL_PROVIDER)
        return NotificationResult(status="failed", error="지원되지 않는 이메일 제공자 설정", failed=len(recipients))

    if not ALERT_EMAIL_FROM or not SENDGRID_API_KEY:
        logger.warning("Email channel is missing SENDGRID_API_KEY or ALERT_EMAIL_FROM.")
        return NotificationResult(status="failed", error="이메일 채널이 구성되지 않았습니다.", failed=len(recipients))

    payload = {
        "personalizations": [{"to": [{"email": email} for email in recipients]}],
        "from": {"email": ALERT_EMAIL_FROM},
        "subject": rendered.get("subject") or "ko-finance 알림",
        "content": [
            {"type": "text/plain", "value": rendered.get("body") or message},
        ],
    }
    html_template = metadata.get("html_template") or metadata.get("html")
    if isinstance(html_template, str):
        html_body = _format_template(html_template, rendered.get("context", {}))
        if html_body:
            payload["content"].append({"type": "text/html", "value": html_body})
    reply_to = metadata.get("reply_to")
    if isinstance(reply_to, str) and reply_to.strip():
        payload["reply_to"] = {"email": reply_to.strip()}
    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json",
    }

    result = _post_with_backoff("https://api.sendgrid.com/v3/mail/send", payload, headers=headers, success_count=len(recipients), result_metadata={"recipients": recipients})
    if result.status == "delivered":
        return result
    return NotificationResult(status=result.status, error=result.error or "이메일 발송 실패", delivered=result.delivered, failed=result.failed or len(recipients), metadata={"recipients": recipients})


def _handle_slack(
    message: str,
    target: Optional[str],
    *,
    targets: Sequence[str],
    metadata: Dict[str, Any],
    rendered: Dict[str, Any],
) -> NotificationResult:
    webhook_candidates = list(targets)
    if not webhook_candidates and ALERT_SLACK_DEFAULT_WEBHOOK:
        webhook_candidates = [ALERT_SLACK_DEFAULT_WEBHOOK]
    results: List[NotificationResult] = []
    for webhook_url in webhook_candidates:
        url = (webhook_url or "").strip()
        if not url:
            results.append(NotificationResult(status="failed", error="Slack Webhook URL이 필요합니다.", failed=1))
            continue
        if not url.startswith("https://"):
            results.append(NotificationResult(status="failed", error="유효한 Slack Webhook URL이 아닙니다.", failed=1))
            continue
        payload: Dict[str, Any] = {"text": rendered.get("body") or message}
        if isinstance(rendered.get("blocks"), list):
            payload["blocks"] = rendered["blocks"]
        attachments = metadata.get("attachments")
        if isinstance(attachments, list):
            payload["attachments"] = attachments
        results.append(
            _post_with_backoff(url, payload, success_count=1, result_metadata={"webhook": url})
        )
    return _aggregate_results(results)


def _handle_webhook(
    message: str,
    target: Optional[str],
    *,
    targets: Sequence[str],
    metadata: Dict[str, Any],
    rendered: Dict[str, Any],
) -> NotificationResult:
    hook_candidates = list(targets)
    extra_urls = metadata.get("urls")
    if not hook_candidates and isinstance(extra_urls, (list, tuple, set)):
        hook_candidates = _unique_targets(None, extra_urls)
    if not hook_candidates and target:
        hook_candidates = [target]
    results: List[NotificationResult] = []
    for url_value in hook_candidates:
        url = (url_value or "").strip()
        if not url:
            results.append(NotificationResult(status="failed", error="Webhook URL이 필요합니다.", failed=1))
            continue
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            results.append(NotificationResult(status="failed", error="지원되지 않는 Webhook 프로토콜입니다.", failed=1))
            continue
        payload_template = metadata.get("payload_template")
        if isinstance(payload_template, dict):
            payload = dict(payload_template)
            payload.setdefault("message", rendered.get("body") or message)
        else:
            payload = {"message": rendered.get("body") or message, "origin": "ko-finance-alerts"}
        results.append(_post_with_backoff(url, payload, success_count=1, result_metadata={"webhook": url}))
    return _aggregate_results(results)


def _handle_pagerduty(
    message: str,
    target: Optional[str],
    *,
    targets: Sequence[str],
    metadata: Dict[str, Any],
    rendered: Dict[str, Any],
) -> NotificationResult:
    routing_keys = list(targets) or _unique_targets(target, None)
    if not routing_keys and PAGERDUTY_ROUTING_KEY:
        routing_keys = [PAGERDUTY_ROUTING_KEY]
    if not routing_keys:
        return NotificationResult(status="failed", error="PagerDuty routing key가 필요합니다.")
    severity = metadata.get("severity", "info")
    source = metadata.get("source", "ko-finance-alerts")
    component = metadata.get("component")
    results: List[NotificationResult] = []
    for key in routing_keys:
        routing_key = (key or "").strip()
        if not routing_key:
            results.append(NotificationResult(status="failed", error="PagerDuty routing key가 필요합니다.", failed=1))
            continue
        payload = {
            "routing_key": routing_key,
            "event_action": "trigger",
            "payload": {
                "summary": (rendered.get("body") or message)[:1024],
                "severity": severity,
                "source": source,
            },
        }
        if component:
            payload["payload"]["component"] = component
        results.append(
            _post_with_backoff(
                "https://events.pagerduty.com/v2/enqueue",
                payload,
                success_count=1,
                result_metadata={"routing_key": routing_key},
            )
        )
    return _aggregate_results(results)


def _post_with_backoff(
    url: str,
    payload: dict,
    *,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = ALERT_WEBHOOK_TIMEOUT,
    max_attempts: int = ALERT_WEBHOOK_RETRIES,
    success_count: int = 1,
    result_metadata: Optional[Dict[str, Any]] = None,
) -> NotificationResult:
    delay = 0.5
    attempts = max(1, max_attempts)
    for attempt in range(1, attempts + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
            return NotificationResult(status="delivered", delivered=success_count, metadata=result_metadata)
        except httpx.HTTPStatusError as exc:
            logger.warning("Notification HTTP error (attempt %s/%s): %s", attempt, attempts, exc.response.text)
            error_message = exc.response.text
        except httpx.RequestError as exc:
            logger.warning("Notification request error (attempt %s/%s): %s", attempt, attempts, exc)
            error_message = str(exc)
        except Exception as exc:  # pragma: no cover - network/JSON errors are best-effort
            logger.error("Notification unexpected error (attempt %s/%s): %s", attempt, attempts, exc, exc_info=True)
            error_message = str(exc)
        if attempt < attempts:
            time.sleep(delay)
            delay *= 2
        else:
            return NotificationResult(status="failed", error=error_message, failed=success_count, metadata=result_metadata)
    return NotificationResult(status="failed", error="알 수 없는 오류", failed=success_count, metadata=result_metadata)


CHANNEL_REGISTRY: Dict[str, Callable[..., NotificationResult]] = {
    "telegram": _handle_telegram,
    "email": _handle_email,
    "slack": _handle_slack,
    "webhook": _handle_webhook,
    "pagerduty": _handle_pagerduty,
}


__all__ = ["dispatch_notification", "send_telegram_alert", "NotificationResult"]
