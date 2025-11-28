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


def build_channel_preview(
    *,
    channel_type: Optional[str],
    message: str,
    metadata: Optional[Dict[str, Any]],
    template: Optional[str],
    message_template: Optional[str],
) -> Dict[str, Any]:
    combined_metadata: Dict[str, Any] = dict(metadata or {})
    if channel_type:
        combined_metadata.setdefault("channel_type", channel_type)

    preview_message = message
    if message_template:
        try:
            preview_message = message_template.format(message=message, **combined_metadata)
        except Exception as exc:  # pragma: no cover - preview should not fail
            logger.debug("Channel preview template failed: %s", exc)
            preview_message = message_template

    rendered = _render_channel_payload(preview_message, combined_metadata, template)
    return {
        "message": preview_message,
        "payload": rendered,
        "templateUsed": template,
    }


def _aggregate_results(results: Sequence[NotificationResult]) -> NotificationResult:
    if not results:
        return NotificationResult(status="failed", error="발송 대상이 없습니다.", delivered=0, failed=0)
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
            payload = {"message": rendered.get("body") or message, "origin": "nuvien-alerts"}
        results.append(_post_with_backoff(url, payload, success_count=1, result_metadata={"webhook": url}))
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
    "slack": _handle_slack,
    "webhook": _handle_webhook,
}


__all__ = ["dispatch_notification", "NotificationResult", "build_channel_preview"]

