"""Utilities for aggregating watchlist alerts and rendering digests."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple
import threading
import time

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.logging import get_logger
from models.alert import AlertDelivery, AlertRule
from core.env import env_int
from services.memory.facade import MEMORY_SERVICE
from services.watchlist_tasks import generate_watchlist_personal_note_task
from services.watchlist_utils import is_watchlist_rule

logger = get_logger(__name__)

PERSONAL_NOTE_MAX_CALLS = env_int("WATCHLIST_PERSONAL_NOTE_MAX_CALLS", 1, minimum=0)
PERSONAL_NOTE_CACHE_SECONDS = env_int("WATCHLIST_PERSONAL_NOTE_CACHE_SECONDS", 3600, minimum=60)
PERSONAL_NOTE_MIN_INTERVAL_SECONDS = env_int("WATCHLIST_PERSONAL_NOTE_MIN_INTERVAL_SECONDS", 2, minimum=0)
PERSONAL_NOTE_TASK_TIMEOUT_SECONDS = env_int("WATCHLIST_PERSONAL_NOTE_TASK_TIMEOUT_SECONDS", 30, minimum=5)

_PERSONAL_NOTE_CACHE_LOCK = threading.Lock()
_PERSONAL_NOTE_CACHE: Dict[str, "PersonalNoteCacheEntry"] = {}
_PERSONAL_NOTE_LAST_CALL = 0.0


def _string_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        data: List[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            trimmed = item.strip()
            if trimmed:
                data.append(trimmed)
        return data
    if isinstance(value, str):
        trimmed = value.strip()
        return [trimmed] if trimmed else []
    return []


def _fetch_recent_deliveries(
    db: Session,
    *,
    window_start: datetime,
    window_end: datetime,
    owner_filters: Optional[Mapping[str, Optional[Any]]] = None,
) -> Sequence[Tuple[AlertDelivery, AlertRule]]:
    query = (
        db.query(AlertDelivery, AlertRule)
        .join(AlertRule, AlertRule.id == AlertDelivery.alert_id)
        .filter(
            AlertDelivery.created_at >= window_start,
            AlertDelivery.created_at <= window_end,
            AlertDelivery.status.in_(["delivered", "failed"]),
        )
        .order_by(AlertDelivery.created_at.desc())
    )
    owner_filters = owner_filters or {}
    user_id = owner_filters.get("user_id")
    org_id = owner_filters.get("org_id")
    if user_id:
        query = query.filter(AlertRule.user_id == user_id)
    if org_id:
        query = query.filter(AlertRule.org_id == org_id)
    return query.all()


def collect_watchlist_alerts(
    db: Session,
    *,
    window_minutes: int = 1440,
    limit: int = 100,
    channels: Optional[Sequence[str]] = None,
    event_types: Optional[Sequence[str]] = None,
    tickers: Optional[Sequence[str]] = None,
    rule_tags: Optional[Sequence[str]] = None,
    min_sentiment: Optional[float] = None,
    max_sentiment: Optional[float] = None,
    query: Optional[str] = None,
    window_start: Optional[datetime] = None,
    window_end: Optional[datetime] = None,
    owner_filters: Optional[Mapping[str, Optional[Any]]] = None,
    plan_memory_enabled: Optional[bool] = None,
    session_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    user_id_hint: Optional[str] = None,
    _rows_override: Optional[Sequence[Tuple[AlertDelivery, AlertRule]]] = None,
) -> Dict[str, Any]:
    """
    Gather watchlist-related alert deliveries within the specified time window.

    Parameters
    ----------
    db:
        SQLAlchemy session.
    window_minutes:
        Lookback window (minutes) used to collect alerts.
    limit:
        Maximum number of individual alert events to include in the response.
    _rows_override:
        Testing hook allowing the caller to supply pre-fetched rows.
    """

    now = datetime.now(timezone.utc)
    limit = max(int(limit or 1), 1)

    normalized_window_end = window_end.astimezone(timezone.utc) if isinstance(window_end, datetime) else now
    normalized_window_start: datetime
    if isinstance(window_start, datetime):
        normalized_window_start = window_start.astimezone(timezone.utc)
    else:
        window_minutes = max(int(window_minutes or 60), 5)
        normalized_window_start = normalized_window_end - timedelta(minutes=window_minutes)

    if normalized_window_start > normalized_window_end:
        normalized_window_start, normalized_window_end = normalized_window_end, normalized_window_start

    effective_window_minutes = max(
        int((normalized_window_end - normalized_window_start).total_seconds() // 60) or 1,
        1,
    )

    normalized_channels: Set[str] = {str(value).strip().lower() for value in (channels or []) if str(value).strip()}
    normalized_event_types: Set[str] = {
        str(value).strip().lower() for value in (event_types or []) if str(value).strip()
    }
    normalized_tickers: Set[str] = {str(value).strip().upper() for value in (tickers or []) if str(value).strip()}
    normalized_rule_tags: Set[str] = {str(value).strip().lower() for value in (rule_tags or []) if str(value).strip()}

    sentiment_min = max(min(min_sentiment, 1.0), -1.0) if isinstance(min_sentiment, (int, float)) else None
    sentiment_max = max(min(max_sentiment, 1.0), -1.0) if isinstance(max_sentiment, (int, float)) else None
    if sentiment_min is not None and sentiment_max is not None and sentiment_min > sentiment_max:
        sentiment_min, sentiment_max = sentiment_max, sentiment_min

    normalized_query = query.strip().lower() if isinstance(query, str) and query.strip() else None

    rows: Sequence[Tuple[AlertDelivery, AlertRule]]
    if _rows_override is not None:
        rows = list(_rows_override)
    else:
        rows = _fetch_recent_deliveries(
            db,
            window_start=normalized_window_start,
            window_end=normalized_window_end,
            owner_filters=owner_filters,
        )

    summary, items = _summarize_watchlist_rows(
        rows,
        window_start=normalized_window_start,
        window_end=normalized_window_end,
        limit=limit,
        filters={
            "channels": normalized_channels,
            "event_types": normalized_event_types,
            "tickers": normalized_tickers,
            "rule_tags": normalized_rule_tags,
            "min_sentiment": sentiment_min,
            "max_sentiment": sentiment_max,
            "query": normalized_query,
        },
    )

    payload = {
        "generatedAt": now.isoformat(),
        "windowMinutes": effective_window_minutes,
        "window": {
            "start": normalized_window_start.isoformat(),
            "end": normalized_window_end.isoformat(),
        },
        "summary": summary,
        "items": items,
    }
    _maybe_capture_watchlist_memory(
        payload,
        plan_memory_enabled=plan_memory_enabled,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id_hint=user_id_hint,
        owner_filters=owner_filters,
    )
    return payload


def _extract_rule_tags(rule: AlertRule) -> List[str]:
    extras = getattr(rule, "extras", {}) or {}
    tags: List[str] = []
    if isinstance(extras, Mapping):
        raw_tags = extras.get("tags") or extras.get("labels") or extras.get("tag_list")
        if isinstance(raw_tags, (list, tuple, set)):
            seen: Set[str] = set()
            for tag in raw_tags:
                if not isinstance(tag, str):
                    continue
                trimmed = tag.strip()
                lowered = trimmed.lower()
                if trimmed and lowered not in seen:
                    seen.add(lowered)
                    tags.append(trimmed)
        elif isinstance(raw_tags, str):
            trimmed = raw_tags.strip()
            if trimmed:
                tags.append(trimmed)
    return tags


def _extract_rule_tickers(rule: AlertRule) -> List[str]:
    trigger_payload = getattr(rule, "trigger", {}) or {}
    raw_tickers = trigger_payload.get("tickers") or []
    tickers: List[str] = []
    if isinstance(raw_tickers, (list, tuple, set)):
        seen: Set[str] = set()
        for value in raw_tickers:
            if not isinstance(value, str):
                continue
            trimmed = value.strip()
            upper = trimmed.upper()
            if trimmed and upper not in seen:
                seen.add(upper)
                tickers.append(upper)
    elif isinstance(raw_tickers, str):
        trimmed = raw_tickers.strip()
        if trimmed:
            tickers.append(trimmed.upper())
    return tickers


def _item_matches_filters(item: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
    channels: Set[str] = filters.get("channels") or set()
    event_types: Set[str] = filters.get("event_types") or set()
    tickers: Set[str] = filters.get("tickers") or set()
    rule_tags: Set[str] = filters.get("rule_tags") or set()
    min_sentiment = filters.get("min_sentiment")
    max_sentiment = filters.get("max_sentiment")
    query = filters.get("query")

    channel = str(item.get("channel") or "").lower()
    if channels and channel not in channels:
        return False

    event_type = str(item.get("eventType") or "").lower()
    if event_types and event_type not in event_types:
        return False

    if tickers:
        item_tickers: Set[str] = set()
        ticker_value = item.get("ticker")
        if isinstance(ticker_value, str):
            item_tickers.add(ticker_value.upper())
        for value in item.get("ruleTickers") or []:
            if isinstance(value, str):
                item_tickers.add(value.upper())
        if not item_tickers.intersection(tickers):
            return False

    if rule_tags:
        item_tags: Set[str] = {str(tag).lower() for tag in (item.get("ruleTags") or []) if isinstance(tag, str)}
        if not item_tags.intersection(rule_tags):
            return False

    sentiment = item.get("sentiment")
    if isinstance(sentiment, (int, float)):
        if min_sentiment is not None and sentiment < min_sentiment:
            return False
        if max_sentiment is not None and sentiment > max_sentiment:
            return False
    else:
        if min_sentiment is not None or max_sentiment is not None:
            return False

    if isinstance(query, str) and query:
        haystack_parts = [
            str(item.get("ruleName") or ""),
            str(item.get("ticker") or ""),
            str(item.get("company") or ""),
            str(item.get("headline") or ""),
        ]
        summary_part = item.get("summary")
        if summary_part:
            haystack_parts.append(str(summary_part))
        message_part = item.get("message")
        if message_part:
            haystack_parts.append(str(message_part))
        category_part = item.get("category")
        if category_part:
            haystack_parts.append(str(category_part))
        haystack = " ".join(haystack_parts).lower()
        if query not in haystack:
            return False

    return True


def _summarize_watchlist_rows(
    rows: Sequence[Tuple[AlertDelivery, AlertRule]],
    *,
    window_start: datetime,
    window_end: datetime,
    limit: int,
    filters: Mapping[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    channel_success_counter: Counter[str] = Counter()
    channel_failure_counter: Counter[str] = Counter()
    rule_success_counter: Counter[str] = Counter()
    ticker_counter: Counter[str] = Counter()
    items: List[Dict[str, Any]] = []
    delivered_ids: Set[str] = set()
    failed_ids: Set[str] = set()

    for delivery, rule in rows:
        if not is_watchlist_rule(rule):
            continue

        rule_label = str(getattr(rule, "name", None) or rule.id)
        delivery_channel = str(getattr(delivery, "channel", "") or "unknown").lower()
        delivery_status = str(getattr(delivery, "status", "") or "unknown").lower()
        delivery_error = getattr(delivery, "error_message", None)
        trigger_payload = getattr(rule, "trigger", {}) or {}
        event_type = str(trigger_payload.get("type") or "filing").lower()
        rule_tags = _extract_rule_tags(rule)
        rule_tickers = _extract_rule_tickers(rule)
        rule_error_count = int(getattr(rule, "error_count", 0) or 0)

        context = getattr(delivery, "context", None)
        events: Iterable[Mapping[str, Any]]
        if isinstance(context, Mapping):
            raw_events = context.get("events")
            if isinstance(raw_events, list):
                events = [event for event in raw_events if isinstance(event, Mapping)]
            else:
                events = []
        else:
            events = []

        delivery_included = False
        channel_for_counter = delivery_channel
        candidate_events: Iterable[Mapping[str, Any]] = events or [{}]

        for event in candidate_events:
            candidate = _build_watchlist_item(
                delivery=delivery,
                rule=rule,
                event_type=event_type,
                event=event,
                rule_tags=rule_tags,
                rule_tickers=rule_tickers,
                delivery_status=delivery_status,
                delivery_error=delivery_error,
                rule_error_count=rule_error_count,
            )
            if not candidate or not _item_matches_filters(candidate, filters):
                continue

            items.append(candidate)
            ticker_value = candidate.get("ticker")
            if isinstance(ticker_value, str) and delivery_status == "delivered":
                ticker_counter[ticker_value.upper()] += 1
            delivery_included = True
            channel_for_counter = str(candidate.get("channel") or delivery_channel).lower()

        if delivery_included:
            delivery_id = str(getattr(delivery, "id", "") or "")
            if delivery_id:
                if delivery_status == "delivered":
                    delivered_ids.add(delivery_id)
                elif delivery_status == "failed":
                    failed_ids.add(delivery_id)
            if delivery_status == "delivered":
                rule_success_counter[rule_label] += 1
                channel_success_counter[channel_for_counter] += 1
            elif delivery_status == "failed":
                channel_failure_counter[channel_for_counter] += 1

    items.sort(key=lambda entry: entry.get("deliveredAt", ""), reverse=True)
    if len(items) > limit:
        items = items[:limit]

    summary = {
        "totalDeliveries": len(delivered_ids),
        "failedDeliveries": len(failed_ids),
        "totalEvents": len(items),
        "uniqueTickers": len(ticker_counter),
        "topTickers": [ticker for ticker, _ in ticker_counter.most_common(5)],
        "topChannels": dict(channel_success_counter),
        "channelFailures": dict(channel_failure_counter),
        "topRules": [rule for rule, _ in rule_success_counter.most_common(5)],
        "windowStart": window_start.isoformat(),
        "windowEnd": window_end.isoformat(),
    }
    return summary, items


def _coerce_identifier(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _resolve_watchlist_subject(
    tenant_id: Optional[str],
    user_id_hint: Optional[str],
    owner_filters: Optional[Mapping[str, Optional[Any]]],
) -> Tuple[Optional[str], Optional[str]]:
    filters = owner_filters or {}
    metadata_tenant = _coerce_identifier(tenant_id) or _coerce_identifier(
        filters.get("org_id") or filters.get("tenant_id")
    )
    metadata_user = _coerce_identifier(user_id_hint) or _coerce_identifier(filters.get("user_id"))
    if not metadata_tenant and metadata_user:
        metadata_tenant = metadata_user
    if not metadata_user and metadata_tenant:
        metadata_user = metadata_tenant
    return metadata_tenant, metadata_user


@dataclass
class PersonalNoteCacheEntry:
    note: str
    expires_at: float


def _personal_note_cache_key(tenant_id: str, user_id: str) -> str:
    return f"{tenant_id}:{user_id}"


def _get_cached_personal_note(tenant_id: str, user_id: str) -> Optional[str]:
    cache_key = _personal_note_cache_key(tenant_id, user_id)
    with _PERSONAL_NOTE_CACHE_LOCK:
        entry = _PERSONAL_NOTE_CACHE.get(cache_key)
        if entry and entry.expires_at > time.time():
            return entry.note
        if entry:
            _PERSONAL_NOTE_CACHE.pop(cache_key, None)
    return None


def _set_cached_personal_note(tenant_id: str, user_id: str, note: str) -> None:
    cache_key = _personal_note_cache_key(tenant_id, user_id)
    with _PERSONAL_NOTE_CACHE_LOCK:
        _PERSONAL_NOTE_CACHE[cache_key] = PersonalNoteCacheEntry(
            note=note,
            expires_at=time.time() + PERSONAL_NOTE_CACHE_SECONDS,
        )


def _build_watchlist_memory_highlights(summary: Mapping[str, Any], items: Sequence[Mapping[str, Any]]) -> List[str]:
    highlights: List[str] = []
    for item in items[:3]:
        ticker = str(item.get("ticker") or item.get("ruleName") or "").strip()
        headline = str(item.get("headline") or item.get("summary") or item.get("message") or "").strip()
        if ticker and headline:
            highlights.append(f"{ticker}: {headline}")
        elif headline:
            highlights.append(headline)
        elif ticker:
            highlights.append(ticker)
    if not highlights:
        deliveries = summary.get("totalDeliveries", 0)
        events = summary.get("totalEvents", 0)
        highlights.append(f"deliveries={deliveries}, events={events}")
    return [highlight for highlight in highlights if highlight]


def _build_watchlist_memory_prompt(summary: Mapping[str, Any]) -> str:
    deliveries = summary.get("totalDeliveries", 0)
    events = summary.get("totalEvents", 0)
    top_tickers = summary.get("topTickers") or []
    ticker_text = ", ".join(top_tickers[:3]) if top_tickers else "없음"
    return (
        "다음 정보를 바탕으로 최근 워치리스트 상황을 두세 문장으로 요약해 주세요.\n"
        f"- 총 알림 수: {deliveries}, 이벤트 수: {events}\n"
        f"- 주목 종목: {ticker_text}\n"
        "각 항목의 의미 있는 변화를 사용자 친화적인 언어로 설명해 주세요."
    )


def _maybe_capture_watchlist_memory(
    payload: Mapping[str, Any],
    *,
    plan_memory_enabled: Optional[bool],
    session_id: Optional[str],
    tenant_id: Optional[str],
    user_id_hint: Optional[str],
    owner_filters: Optional[Mapping[str, Optional[Any]]] = None,
) -> None:
    if not MEMORY_SERVICE.is_enabled(
        plan_memory_enabled=plan_memory_enabled,
        watchlist_context=True,
    ):
        return

    metadata_tenant, metadata_user = _resolve_watchlist_subject(tenant_id, user_id_hint, owner_filters)
    if not metadata_tenant or not metadata_user:
        return

    summary = payload.get("summary") or {}
    items = payload.get("items") or []
    highlights = _build_watchlist_memory_highlights(summary, items)
    if not highlights:
        return

    session_key = session_id or f"watchlist:radar:{metadata_tenant or metadata_user}"
    tenant_value = (metadata_tenant or metadata_user or "").strip()
    user_value = (metadata_user or metadata_tenant or "").strip()
    if not tenant_value or not user_value:
        return

    metadata = {
        "tenant_id": tenant_value,
        "user_id": user_value,
        "window_minutes": str(payload.get("windowMinutes") or ""),
        "importance_score": str(summary.get("totalDeliveries", 0)),
    }

    MEMORY_SERVICE.save_session_summary(
        session_id=session_key,
        topic="watchlist.radar",
        highlights=highlights,
        metadata=metadata,
    )

    try:
        composition = MEMORY_SERVICE.compose_prompt(
            base_prompt=_build_watchlist_memory_prompt(summary),
            session_id=session_key,
            tenant_id=tenant_value,
            user_id=user_value,
            rag_snippets=highlights[:2],
            plan_memory_enabled=plan_memory_enabled,
            watchlist_context=True,
        )
        logger.debug("Composed watchlist memory prompt for session %s.", session_key)
        _ = composition
    except Exception:  # pragma: no cover - best-effort logging
        logger.debug("Watchlist memory prompt composition failed.", exc_info=True)


def _build_personalized_watchlist_note(
    payload: Mapping[str, Any],
    *,
    plan_memory_enabled: Optional[bool],
    session_id: Optional[str],
    tenant_id: Optional[str],
    user_id_hint: Optional[str],
    owner_filters: Mapping[str, Optional[Any]],
    budget: Dict[str, int],
) -> Optional[str]:
    if PERSONAL_NOTE_MAX_CALLS <= 0:
        return None
    used = budget.get("used", 0)
    if used >= PERSONAL_NOTE_MAX_CALLS:
        logger.debug("Skipping watchlist personal note; budget exhausted.")
        return None
    if not MEMORY_SERVICE.is_enabled(
        plan_memory_enabled=plan_memory_enabled,
        watchlist_context=True,
    ):
        return None
    summary = payload.get("summary") or {}
    items = payload.get("items") or []
    if not items:
        return None

    tenant_value, user_value = _resolve_watchlist_subject(tenant_id, user_id_hint, owner_filters)
    if not tenant_value or not user_value:
        return None

    cached = _get_cached_personal_note(tenant_value, user_value)
    if cached:
        logger.debug("Returning cached personal note for tenant=%s user=%s.", tenant_value, user_value)
        return cached

    global _PERSONAL_NOTE_LAST_CALL
    now = time.time()
    if PERSONAL_NOTE_MIN_INTERVAL_SECONDS > 0 and now - _PERSONAL_NOTE_LAST_CALL < PERSONAL_NOTE_MIN_INTERVAL_SECONDS:
        logger.debug("Skipping personal note due to rate limit window.")
        return None

    session_key = session_id or f"watchlist:personal:{tenant_value}"
    highlights = _build_watchlist_memory_highlights(summary, items)
    try:
        composition = MEMORY_SERVICE.compose_prompt(
            base_prompt=_build_watchlist_memory_prompt(summary),
            session_id=session_key,
            tenant_id=tenant_value,
            user_id=user_value,
            rag_snippets=highlights[:3],
            plan_memory_enabled=plan_memory_enabled,
            watchlist_context=True,
        )
        prompt_text = composition.build()
    except Exception as exc:
        logger.debug("Watchlist personal prompt composition failed: %s", exc, exc_info=True)
        return None

    try:
        async_result = generate_watchlist_personal_note_task.delay(prompt_text)
        task_payload = async_result.get(timeout=PERSONAL_NOTE_TASK_TIMEOUT_SECONDS)
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Watchlist personal note task failed: %s", exc, exc_info=True)
        return None

    note = (task_payload or {}).get("note")
    meta = (task_payload or {}).get("meta") or {}
    usage = meta.get("usage") or {}
    if not note:
        return None

    budget["used"] = used + 1
    _set_cached_personal_note(tenant_value, user_value, note)
    _PERSONAL_NOTE_LAST_CALL = now

    logger.info(
        "watchlist.personal_note.generated",
        extra={
            "tenant_id": tenant_value,
            "user_id": user_value,
            "model": meta.get("model"),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
    )
    return note


def _build_watchlist_item(
    *,
    delivery: AlertDelivery,
    rule: AlertRule,
    event_type: str,
    event: Mapping[str, Any],
    rule_tags: Sequence[str],
    rule_tickers: Sequence[str],
    delivery_status: str,
    delivery_error: Optional[str],
    rule_error_count: int,
) -> Optional[Dict[str, Any]]:
    message = str(getattr(delivery, "message", "") or "")
    delivered_at = getattr(delivery, "created_at", None)
    delivered_iso = (
        delivered_at.astimezone(timezone.utc).isoformat()
        if isinstance(delivered_at, datetime)
        else datetime.now(timezone.utc).isoformat()
    )
    ticker = event.get("ticker")
    if isinstance(ticker, str):
        ticker = ticker.strip() or None
    if not ticker and rule_tickers:
        ticker = rule_tickers[0]

    company = event.get("corp_name")
    category = event.get("category")
    headline = event.get("headline")
    summary = event.get("summary")
    source = event.get("source")
    sentiment = event.get("sentiment")
    primary_text = headline or summary or event.get("report_name") or category or message
    url = event.get("url")
    event_time = event.get("filed_at") or event.get("published_at")

    item = {
        "deliveryId": str(getattr(delivery, "id", "")),
        "ruleId": str(getattr(rule, "id", "")),
        "ruleName": str(getattr(rule, "name", "") or getattr(rule, "id", "")),
        "channel": str(getattr(delivery, "channel", "") or "unknown").lower(),
        "eventType": event_type,
        "ruleTags": list(rule_tags),
        "ruleTickers": list(rule_tickers),
        "deliveryStatus": delivery_status,
        "deliveryError": str(delivery_error).strip() if isinstance(delivery_error, str) and delivery_error.strip() else None,
        "ruleErrorCount": rule_error_count,
        "ticker": ticker,
        "company": company,
        "category": category,
        "source": source,
        "headline": headline,
        "summary": primary_text,
        "sentiment": sentiment if isinstance(sentiment, (int, float)) else None,
        "message": message,
        "deliveredAt": delivered_iso,
        "eventTime": event_time,
        "url": url,
    }
    return item


def collect_watchlist_rule_detail(
    db: Session,
    *,
    rule_id,
    owner_filters: Optional[Mapping[str, Optional[Any]]] = None,
    recent_limit: int = 5,
) -> Dict[str, Any]:
    """
    Gather detailed information about a single watchlist rule and its recent deliveries.
    """

    recent_limit = max(min(int(recent_limit or 5), 50), 1)

    query = db.query(AlertRule).filter(AlertRule.id == rule_id)
    owner_filters = owner_filters or {}
    user_id = owner_filters.get("user_id")
    org_id = owner_filters.get("org_id")
    if user_id:
        query = query.filter(AlertRule.user_id == user_id)
    if org_id:
        query = query.filter(AlertRule.org_id == org_id)

    rule = query.first()
    if rule is None:
        raise ValueError("watchlist.rule_not_found")
    if not is_watchlist_rule(rule):
        raise ValueError("watchlist.rule_not_watchlist")

    trigger_raw = getattr(rule, "trigger", {}) or {}
    trigger_detail = {
        "type": str(trigger_raw.get("type") or "filing"),
        "tickers": _string_list(trigger_raw.get("tickers")),
        "categories": _string_list(trigger_raw.get("categories")),
        "sectors": _string_list(trigger_raw.get("sectors")),
        "minSentiment": trigger_raw.get("minSentiment"),
    }

    channels_raw = getattr(rule, "channels", []) or []
    channel_details: List[Dict[str, Any]] = []
    if isinstance(channels_raw, list):
        for entry in channels_raw:
            if not isinstance(entry, Mapping):
                continue
            channel_details.append(
                {
                    "type": str(entry.get("type") or ""),
                    "label": entry.get("label"),
                    "target": entry.get("target"),
                    "targets": _string_list(entry.get("targets")),
                    "metadata": entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {},
                }
            )

    extras = getattr(rule, "extras", {}) or {}
    if not isinstance(extras, dict):
        extras = {}

    deliveries_query = (
        db.query(AlertDelivery)
        .filter(AlertDelivery.alert_id == rule.id)
        .order_by(AlertDelivery.created_at.desc())
        .limit(recent_limit)
    )
    deliveries = deliveries_query.all()

    status_counts = (
        db.query(AlertDelivery.status, func.count())
        .filter(AlertDelivery.alert_id == rule.id)
        .group_by(AlertDelivery.status)
        .all()
    )
    total_deliveries = 0
    failed_deliveries = 0
    for status, count in status_counts:
        status_value = str(status or "").lower()
        if status_value == "delivered":
            total_deliveries += int(count or 0)
        elif status_value == "failed":
            failed_deliveries += int(count or 0)

    def _iso(dt: Optional[datetime]) -> Optional[str]:
        if isinstance(dt, datetime):
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc).isoformat()
            return dt.astimezone(timezone.utc).isoformat()
        return None

    delivery_logs: List[Dict[str, Any]] = []
    for delivery in deliveries:
        delivery_events: List[Dict[str, Any]] = []
        context = getattr(delivery, "context", None)
        if isinstance(context, Mapping):
            raw_events = context.get("events")
            if isinstance(raw_events, list):
                for event in raw_events:
                    if not isinstance(event, Mapping):
                        continue
                    delivery_events.append(
                        {
                            "ticker": event.get("ticker"),
                            "headline": event.get("headline") or event.get("summary"),
                            "summary": event.get("summary"),
                            "sentiment": event.get("sentiment") if isinstance(event.get("sentiment"), (int, float)) else None,
                            "category": event.get("category"),
                            "url": event.get("url"),
                            "eventTime": event.get("filed_at") or event.get("published_at") or event.get("event_time"),
                        }
                    )

        delivered_at = getattr(delivery, "created_at", None)
        error_message = getattr(delivery, "error_message", None)
        if isinstance(error_message, str):
            error_message = error_message.strip() or None
        delivery_logs.append(
            {
                "deliveryId": str(getattr(delivery, "id", "")),
                "channel": str(getattr(delivery, "channel", "") or "unknown").lower(),
                "status": str(getattr(delivery, "status", "") or "").lower(),
                "deliveredAt": _iso(delivered_at) or datetime.now(timezone.utc).isoformat(),
                "error": error_message,
                "eventCount": len(delivery_events),
                "events": delivery_events,
            }
        )

    rule_detail = {
        "id": str(getattr(rule, "id", "")),
        "name": str(getattr(rule, "name", "") or ""),
        "description": getattr(rule, "description", None),
        "status": str(getattr(rule, "status", "")),
        "evaluationIntervalMinutes": int(getattr(rule, "evaluation_interval_minutes", 0) or 0),
        "windowMinutes": int(getattr(rule, "window_minutes", 0) or 0),
        "cooldownMinutes": int(getattr(rule, "cooldown_minutes", 0) or 0),
        "maxTriggersPerDay": getattr(rule, "max_triggers_per_day", None),
        "trigger": trigger_detail,
        "channels": channel_details,
        "extras": extras,
        "lastTriggeredAt": _iso(getattr(rule, "last_triggered_at", None)),
        "lastEvaluatedAt": _iso(getattr(rule, "last_evaluated_at", None)),
        "errorCount": int(getattr(rule, "error_count", 0) or 0),
    }

    return {
        "rule": rule_detail,
        "recentDeliveries": delivery_logs,
        "totalDeliveries": total_deliveries,
        "failedDeliveries": failed_deliveries,
    }


__all__ = [
    "collect_watchlist_alerts",
    "is_watchlist_rule",
    "collect_watchlist_rule_detail",
]
