"""Business logic for alert rule management and dispatch."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
import time
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from dataclasses import dataclass, field

from sqlalchemy import and_, func, or_, case
from sqlalchemy.orm import Session

from alerts.rule_compiler import CompiledRulePlan, compile_trigger, plan_signature, snapshot_digest
from core.env import env_bool, env_int
from models.alert import AlertDelivery, AlertRule
from models.event_study import EventAlertMatch, EventRecord
from models.filing import Filing
from models.news import NewsSignal
from services import alert_metrics, quota_guard
from services.notification_service import NotificationResult, dispatch_notification
from services.alert_channel_registry import validate_channel_payload
from services.audit_log import audit_alert_event
logger = logging.getLogger(__name__)

ALERTS_ENABLE_MODEL = env_bool("ALERTS_ENABLE_MODEL", True)
ALERTS_ENFORCE_RL = env_bool("ALERTS_ENFORCE_RL", False)
ALERT_CHANNEL_FAILURE_COOLDOWN_MINUTES = env_int("ALERTS_CHANNEL_FAILURE_COOLDOWN_MINUTES", 15, minimum=1)
ENTITLEMENT_ACTION_RULE_WRITE = "alerts.rules.max"

ERROR_BACKOFF_SEQUENCE = (5, 15, 60)
_VALID_TRIGGER_TYPES = {"filing", "news", "event"}
PLAN_CONSTRAINTS: Dict[str, Dict[str, Any]] = {
    "free": {
        "max_alerts": 3,
        "channels": ("email",),
        "default_evaluation_interval_minutes": 30,
        "default_window_minutes": 720,
        "default_cooldown_minutes": 180,
        "min_cooldown_minutes": 30,
        "min_evaluation_interval_minutes": 15,
        "max_daily_triggers": 10,
    },
    "starter": {
        "max_alerts": 5,
        "channels": ("email", "telegram"),
        "default_evaluation_interval_minutes": 15,
        "default_window_minutes": 360,
        "default_cooldown_minutes": 120,
        "min_cooldown_minutes": 15,
        "min_evaluation_interval_minutes": 5,
        "max_daily_triggers": 20,
    },
    "pro": {
        "max_alerts": 10,
        "channels": ("email", "telegram"),
        "default_evaluation_interval_minutes": 5,
        "default_window_minutes": 120,
        "default_cooldown_minutes": 60,
        "min_cooldown_minutes": 15,
        "min_evaluation_interval_minutes": 5,
        "max_daily_triggers": 50,
    },
    "enterprise": {
        "max_alerts": 1000,
        "channels": ("email", "telegram", "slack", "webhook", "pagerduty"),
        "default_evaluation_interval_minutes": 3,
        "default_window_minutes": 90,
        "default_cooldown_minutes": 30,
        "min_cooldown_minutes": 5,
        "min_evaluation_interval_minutes": 1,
        "max_daily_triggers": 500,
    },
}

DEFAULT_PLAN_KEY = "pro"

LEGACY_FREQUENCY_FIELDS = {
    "evaluation_interval_minutes": "evaluationIntervalMinutes",
    "window_minutes": "windowMinutes",
    "cooldown_minutes": "cooldownMinutes",
    "max_triggers_per_day": "maxTriggersPerDay",
}

DEFAULT_MESSAGE = "새로운 알림이 감지되었습니다."
_EVAL_STATE_KEY = "alertWorkerState"
_EVAL_STATE_VERSION = 1
_MAX_STATE_EVENT_IDS = 50


class PlanQuotaError(RuntimeError):
    """Raised when the current plan does not allow the requested action."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def allowed_channels(plan_tier: str) -> Sequence[str]:
    return tuple(_plan_config(plan_tier)["channels"])


def max_alerts_for_plan(plan_tier: str) -> int:
    return int(_plan_config(plan_tier)["max_alerts"])


def _plan_config(plan_tier: str) -> Dict[str, Any]:
    return PLAN_CONSTRAINTS.get(plan_tier, PLAN_CONSTRAINTS[DEFAULT_PLAN_KEY])


def _normalize_plan_tier(plan_tier: str) -> str:
    if plan_tier in PLAN_CONSTRAINTS:
        return plan_tier
    return DEFAULT_PLAN_KEY


def _normalize_trigger_type(value: Any) -> str:
    if isinstance(value, str):
        candidate = value.strip().lower()
    else:
        candidate = ""
    return candidate if candidate in _VALID_TRIGGER_TYPES else "filing"


def _normalize_filters(trigger_payload: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(trigger_payload, Mapping):
        return {}

    def _clean_list(raw: Any) -> List[str]:
        if raw is None:
            return []
        if isinstance(raw, str):
            raw_values = [raw]
        else:
            raw_values = list(raw) if isinstance(raw, (list, tuple, set)) else []
        cleaned: List[str] = []
        for item in raw_values:
            if not isinstance(item, str):
                continue
            text = item.strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned

    filters: Dict[str, Any] = {}
    for key in ("tickers", "categories", "sectors", "keywords", "entities"):
        values = _clean_list(trigger_payload.get(key))
        if values:
            filters[key] = values
    sentiment = trigger_payload.get("minSentiment")
    if isinstance(sentiment, (int, float)):
        filters["minSentiment"] = float(sentiment)
    dsl = trigger_payload.get("dsl")
    if isinstance(dsl, str) and dsl.strip():
        filters["dsl"] = dsl.strip()
    return filters


def _refresh_rule_filters(rule: AlertRule) -> None:
    trigger_payload = rule.trigger if isinstance(rule.trigger, Mapping) else {}
    rule.trigger_type = _normalize_trigger_type(trigger_payload.get("type"))
    rule.filters = _normalize_filters(trigger_payload)


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _channel_cooldown_until(state: Mapping[str, Any], channel_type: str, now: datetime) -> Optional[datetime]:
    entry = state.get(channel_type)
    if not isinstance(entry, Mapping):
        return None
    retry_at = _parse_iso_datetime(entry.get("retryAfter"))
    if retry_at and retry_at > now:
        return retry_at
    return None


def _normalize_uuid(value: Any) -> Optional[uuid.UUID]:
    if not value:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _resolve_subject(owner_filters: Mapping[str, Any]) -> Tuple[Optional[uuid.UUID], Optional[uuid.UUID]]:
    user_id = _normalize_uuid(owner_filters.get("user_id"))
    org_id = _normalize_uuid(owner_filters.get("org_id"))
    if user_id is None and org_id is not None:
        user_id = org_id
    if org_id is None and user_id is not None:
        org_id = user_id
    return user_id, org_id


def _consume_entitlement(
    owner_filters: Mapping[str, Any],
    *,
    action: str,
    cost: int = 1,
) -> None:
    if not ALERTS_ENFORCE_RL:
        return
    allowed = quota_guard.consume_quota(
        action,
        user_id=owner_filters.get("user_id"),
        org_id=owner_filters.get("org_id"),
        cost=cost,
        context="alerts.service",
    )
    if not allowed:
        raise PlanQuotaError("plan.entitlement_blocked", "플랜 할당량을 초과했습니다.")


def _error_backoff_minutes(error_count: int) -> int:
    """Compute cooldown minutes applied after consecutive failures."""
    if error_count <= 0:
        return 0
    index = min(error_count - 1, len(ERROR_BACKOFF_SEQUENCE) - 1)
    return ERROR_BACKOFF_SEQUENCE[index]


def ensure_plan_allows_creation(db: Session, *, plan_tier: str, owner_filters: Dict[str, Any]) -> None:
    """Validate alert quota before creating a new rule."""
    limit = max_alerts_for_plan(plan_tier)
    if limit == 0:
        raise PlanQuotaError("plan.quota_unavailable", "현재 플랜에서는 알림이 제공되지 않습니다.")
    count = _count_alerts(db, owner_filters)
    if count >= limit:
        raise PlanQuotaError("plan.quota_exceeded", "플랜 알림 한도를 초과했습니다.")
    _consume_entitlement(owner_filters, action=ENTITLEMENT_ACTION_RULE_WRITE)


def _count_alerts(db: Session, owner_filters: Dict[str, Any]) -> int:
    query = db.query(func.count(AlertRule.id)).filter(AlertRule.status != "archived")
    for column, value in owner_filters.items():
        if value is None:
            query = query.filter(getattr(AlertRule, column).is_(None))
        else:
            query = query.filter(getattr(AlertRule, column) == value)
    return int(query.scalar() or 0)


def validate_channels(plan_tier: str, channels: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    permitted = set(allowed_channels(plan_tier))
    normalized: List[Dict[str, Any]] = []
    for config in channels:
        if not isinstance(config, dict):
            raise ValueError("채널 설정이 정상적인 형태가 아닙니다.")
        channel_type = str(config.get("type", "")).lower().strip()
        if channel_type not in permitted:
            raise PlanQuotaError("plan.channel_not_permitted", f"{plan_tier} 플랜에서는 {channel_type} 채널을 사용할 수 없습니다.")
        raw_target = config.get("target")
        aggregated_targets: List[str] = []
        if isinstance(raw_target, str):
            candidate = raw_target.strip()
            if candidate:
                aggregated_targets.append(candidate)
        raw_targets = config.get("targets") or []
        if isinstance(raw_targets, (list, tuple, set)):
            for item in raw_targets:
                if not isinstance(item, str):
                    continue
                candidate = item.strip()
                if candidate and candidate not in aggregated_targets:
                    aggregated_targets.append(candidate)
        metadata_payload = config.get("metadata") if isinstance(config.get("metadata"), dict) else {}
        sanitized_metadata = validate_channel_payload(channel_type, aggregated_targets, metadata_payload)
        entry: Dict[str, Any] = {"type": channel_type}
        if aggregated_targets:
            entry["target"] = aggregated_targets[0]
            entry["targets"] = aggregated_targets
        label_raw = str(config.get("label") or "").strip()
        if label_raw:
            entry["label"] = label_raw
        template_raw = str(config.get("template") or "").strip()
        if template_raw:
            entry["template"] = template_raw
        if sanitized_metadata:
            entry["metadata"] = sanitized_metadata
        normalized.append(entry)
    if not normalized:
        raise ValueError("최소한 한 개 이상의 채널을 선택해야 합니다.")
    return normalized

def list_alert_rules(
    db: Session,
    *,
    owner_filters: Dict[str, Any],
    status: Optional[str] = None,
) -> List[AlertRule]:
    query = db.query(AlertRule)
    for column, value in owner_filters.items():
        if value is None:
            query = query.filter(getattr(AlertRule, column).is_(None))
        else:
            query = query.filter(getattr(AlertRule, column) == value)
    if status:
        query = query.filter(AlertRule.status == status)
    query = query.order_by(AlertRule.created_at.desc())
    return list(query.all())


def get_alert_rule(
    db: Session,
    *,
    rule_id: uuid.UUID,
    owner_filters: Dict[str, Any],
) -> Optional[AlertRule]:
    query = db.query(AlertRule).filter(AlertRule.id == rule_id)
    for column, value in owner_filters.items():
        if value is None:
            query = query.filter(getattr(AlertRule, column).is_(None))
        else:
            query = query.filter(getattr(AlertRule, column) == value)
    return query.first()


def create_alert_rule(
    db: Session,
    *,
    plan_tier: str,
    owner_filters: Dict[str, Any],
    name: str,
    description: Optional[str],
    trigger: Mapping[str, Any],
    channels: Sequence[Dict[str, Any]],
    message_template: Optional[str],
    frequency: Mapping[str, Any],
    extras: Optional[Dict[str, Any]] = None,
) -> AlertRule:
    plan_tier = _normalize_plan_tier(plan_tier)
    ensure_plan_allows_creation(db, plan_tier=plan_tier, owner_filters=owner_filters)
    normalized_channels = validate_channels(plan_tier, channels)
    normalized_frequency = _apply_plan_frequency(plan_tier, frequency)

    trigger_payload = dict(trigger or {})
    rule = AlertRule(
        plan_tier=plan_tier,
        name=name.strip(),
        description=description.strip() if description else None,
        trigger=trigger_payload,
        trigger_type=_normalize_trigger_type(trigger_payload.get("type")),
        filters=_normalize_filters(trigger_payload),
        channels=normalized_channels,
        message_template=message_template.strip() if message_template else None,
        frequency=normalized_frequency,
        extras=extras or {},
        **owner_filters,
    )
    db.add(rule)
    return rule


def update_alert_rule(
    db: Session,
    *,
    rule: AlertRule,
    plan_tier: str,
    changes: Dict[str, Any],
) -> AlertRule:
    plan_tier = _normalize_plan_tier(plan_tier)
    trigger_updated = False
    if "name" in changes and changes["name"]:
        rule.name = str(changes["name"]).strip()
    if "description" in changes:
        description = changes["description"]
        rule.description = description.strip() if description else None
    if "trigger" in changes and changes["trigger"]:
        rule.condition = dict(changes["trigger"] or {})
        trigger_updated = True
    elif "condition" in changes and changes["condition"]:
        rule.condition = dict(changes["condition"] or {})
        trigger_updated = True
    if "channels" in changes and changes["channels"] is not None:
        rule.channels = validate_channels(plan_tier, changes["channels"])
    if "message_template" in changes:
        message = changes["message_template"]
        rule.message_template = message.strip() if message else None
    if "status" in changes and changes["status"] in {"active", "paused", "archived"}:
        rule.status = changes["status"]
    frequency_payload: Optional[Mapping[str, Any]] = None
    if "frequency" in changes and isinstance(changes["frequency"], Mapping):
        frequency_payload = changes["frequency"]
    else:
        legacy: Dict[str, Any] = {}
        for legacy_key, camel_key in LEGACY_FREQUENCY_FIELDS.items():
            if legacy_key in changes:
                legacy[camel_key] = changes[legacy_key]
        if legacy:
            frequency_payload = legacy
    if frequency_payload is not None:
        rule.frequency = _apply_plan_frequency(plan_tier, frequency_payload)
    if "extras" in changes and isinstance(changes["extras"], dict):
        rule.extras = {**rule.extras, **changes["extras"]}
    if trigger_updated:
        _refresh_rule_filters(rule)
    return rule


def archive_alert_rule(db: Session, *, rule: AlertRule) -> None:
    rule.status = "archived"


def _window_start(rule: AlertRule, now: datetime, override_minutes: Optional[int] = None) -> datetime:
    window = override_minutes if override_minutes is not None else rule.window_minutes
    window = max(window or 60, 5)
    return now - timedelta(minutes=window)


def _apply_daily_cap(db: Session, rule: AlertRule, now: datetime) -> bool:
    if not rule.max_triggers_per_day:
        return True
    start_of_day = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    count = (
        db.query(func.count(AlertDelivery.id))
        .filter(
            AlertDelivery.alert_id == rule.id,
            AlertDelivery.status == "delivered",
            AlertDelivery.created_at >= start_of_day,
        )
        .scalar()
    )
    return (count or 0) < rule.max_triggers_per_day


def _query_filings(
    db: Session,
    *,
    tickers: Sequence[str],
    categories: Sequence[str],
    keywords: Sequence[str],
    entities: Sequence[str],
    since: datetime,
) -> List[Filing]:
    since_naive = since.replace(tzinfo=None)
    query = db.query(Filing).filter(Filing.filed_at.isnot(None))
    query = query.filter(Filing.filed_at >= since_naive)
    if tickers:
        query = query.filter(Filing.ticker.in_(tickers))
    if categories:
        query = query.filter(Filing.category.in_(categories))
    if keywords:
        keyword_clauses = []
        for keyword in keywords:
            lowered = keyword.lower()
            pattern = f"%{lowered}%"
            keyword_clauses.append(func.lower(Filing.report_name).like(pattern))
            keyword_clauses.append(func.lower(Filing.title).like(pattern))
        query = query.filter(or_(*keyword_clauses))
    if entities:
        entity_clauses = []
        for entity in entities:
            lowered = entity.lower()
            pattern = f"%{lowered}%"
            entity_clauses.append(func.lower(Filing.corp_name).like(pattern))
        query = query.filter(or_(*entity_clauses))
    query = query.order_by(Filing.filed_at.desc())
    return list(query.limit(10).all())


def _query_news(
    db: Session,
    *,
    tickers: Sequence[str],
    sectors: Sequence[str],
    keywords: Sequence[str],
    entities: Sequence[str],
    min_sentiment: Optional[float],
    since: datetime,
) -> List[NewsSignal]:
    query = db.query(NewsSignal).filter(NewsSignal.published_at >= since)
    if tickers:
        query = query.filter(NewsSignal.ticker.in_(tickers))
    if sectors:
        query = query.filter(or_(NewsSignal.sector.in_(sectors), NewsSignal.industry.in_(sectors)))
    if keywords:
        keyword_clauses = []
        for keyword in keywords:
            lowered = keyword.lower()
            pattern = f"%{lowered}%"
            keyword_clauses.append(func.lower(NewsSignal.headline).like(pattern))
            keyword_clauses.append(func.lower(NewsSignal.summary).like(pattern))
        query = query.filter(or_(*keyword_clauses))
    if entities:
        entity_clauses = []
        ticker_matches: List[str] = []
        for entity in entities:
            lowered = entity.lower()
            if entity.upper() == entity and 1 <= len(entity) <= 6:
                ticker_matches.append(entity)
            pattern = f"%{lowered}%"
            entity_clauses.append(func.lower(NewsSignal.headline).like(pattern))
            entity_clauses.append(func.lower(NewsSignal.summary).like(pattern))
        combined_filters = list(entity_clauses)
        if ticker_matches:
            combined_filters.append(NewsSignal.ticker.in_(ticker_matches))
        if combined_filters:
            query = query.filter(or_(*combined_filters))
    if min_sentiment is not None:
        query = query.filter(NewsSignal.sentiment.isnot(None), NewsSignal.sentiment >= float(min_sentiment))
    query = query.order_by(NewsSignal.published_at.desc())
    return list(query.limit(10).all())


def _build_event_context(events: Sequence[Any], event_type: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for event in events:
        if event_type == "filing":
            results.append(
                {
                    "id": str(event.id),
                    "ticker": event.ticker,
                    "corp_name": event.corp_name,
                    "report_name": event.report_name,
                    "filed_at": event.filed_at.isoformat() if event.filed_at else None,
                    "category": event.category,
                }
            )
        elif event_type == "news":
            published_at = event.published_at
            if published_at and published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            results.append(
                {
                    "id": str(event.id),
                    "ticker": event.ticker,
                    "headline": event.headline,
                    "sentiment": event.sentiment,
                    "source": event.source,
                    "published_at": published_at.isoformat() if published_at else None,
                    "url": event.url,
                }
            )
    return results


def _render_message(rule: AlertRule, events: Sequence[Any], event_type: str) -> str:
    if rule.message_template:
        try:
            # Provide limited context for template formatting.
            first = events[0] if events else None
            context = {
                "event_type": event_type,
                "event_count": len(events),
                "first": first,
            }
            return rule.message_template.format(**context)
        except Exception as exc:  # pragma: no cover - template errors should not crash delivery
            logger.warning("Failed to render alert template %s: %s", rule.id, exc)
    if event_type == "filing" and events:
        filing = events[0]
        corp = filing.corp_name or filing.ticker or "기업"
        label = filing.report_name or filing.category or "공시"
        return f"[공시 알림] {corp} {label}"
    if event_type == "news" and events:
        news = events[0]
        ticker = news.ticker or "종목"
        return f"[뉴스 알림] {ticker} 관련 긍정 뉴스 {len(events)}건"
    return DEFAULT_MESSAGE


def _send_via_channel(channel: Dict[str, Any], message: str) -> NotificationResult:
    """Send the alert message through the requested channel."""
    channel_type = str(channel.get("type", "")).lower().strip()
    target = channel.get("target")
    targets = channel.get("targets")
    metadata = channel.get("metadata") if isinstance(channel.get("metadata"), dict) else {}
    template = channel.get("template")
    return dispatch_notification(
        channel_type,
        message,
        target,
        targets=targets,
        metadata=metadata,
        template=template,
    )


def _record_delivery(
    db: Session,
    *,
    rule: AlertRule,
    channel: Dict[str, Any],
    status: str,
    message: str,
    events: Sequence[Dict[str, Any]],
    error_message: Optional[str],
    delivery: NotificationResult,
    event_ref: Optional[Mapping[str, Any]] = None,
    trigger_hash: Optional[str] = None,
) -> AlertDelivery:
    record = AlertDelivery(
        alert_id=rule.id,
        channel=channel.get("type"),
        status=status,
        message=message,
        context={
            "target": channel.get("target"),
            "targets": channel.get("targets"),
            "events": events,
            "delivery": {
                "delivered": delivery.delivered,
                "failed": delivery.failed,
                "metadata": delivery.metadata,
            },
        },
        error_message=error_message,
        event_ref=dict(event_ref) if isinstance(event_ref, Mapping) else None,
        trigger_hash=trigger_hash,
    )
    db.add(record)
    return record


@dataclass
class _RuleSnapshot:
    plan_signature: str
    event_hash: str
    event_ids: Tuple[str, ...]
    event_count: int
    window_minutes: int
    window_start: datetime
    evaluated_at: datetime

    def as_dict(self) -> Dict[str, Any]:
        return {
            "version": 1,
            "planSignature": self.plan_signature,
            "eventHash": self.event_hash,
            "eventIds": list(self.event_ids),
            "eventCount": self.event_count,
            "windowMinutes": self.window_minutes,
            "windowStart": self.window_start.isoformat(),
            "evaluatedAt": self.evaluated_at.isoformat(),
        }

    @property
    def has_events(self) -> bool:
        return self.event_count > 0


@dataclass
class _RuleEvaluationResult:
    plan: CompiledRulePlan
    event_type: str
    events: Sequence[Any]
    events_json: List[Dict[str, Any]]
    message: str
    matches: bool
    window_start: datetime
    snapshot: _RuleSnapshot


@dataclass
class _PlanEvaluationStats:
    evaluated: int = 0
    triggered: int = 0
    skipped: int = 0
    errors: int = 0
    duplicates: int = 0
    channel_failures: int = 0


@dataclass
class _EvaluationAccumulator:
    evaluated: int = 0
    triggered: int = 0
    skipped: int = 0
    errors: int = 0
    duplicates: int = 0
    by_plan: Dict[str, _PlanEvaluationStats] = field(default_factory=dict)
    channel_failures: List[Dict[str, Any]] = field(default_factory=list)

    def _plan(self, plan_tier: str) -> _PlanEvaluationStats:
        if plan_tier not in self.by_plan:
            self.by_plan[plan_tier] = _PlanEvaluationStats()
        return self.by_plan[plan_tier]

    def record_evaluated(self, plan_tier: str) -> None:
        self.evaluated += 1
        self._plan(plan_tier).evaluated += 1

    def record_skipped(self, plan_tier: str) -> None:
        self.skipped += 1
        self._plan(plan_tier).skipped += 1

    def record_triggered(self, plan_tier: str) -> None:
        self.triggered += 1
        self._plan(plan_tier).triggered += 1

    def record_error(self, plan_tier: str) -> None:
        self.errors += 1
        self._plan(plan_tier).errors += 1

    def record_duplicate(self, plan_tier: str) -> None:
        self.duplicates += 1
        self._plan(plan_tier).duplicates += 1

    def record_channel_failure(self, rule: AlertRule, failures: Sequence[Mapping[str, Any]]) -> None:
        if not failures:
            return
        plan_stats = self._plan(rule.plan_tier)
        plan_stats.channel_failures += len(failures)
        self.channel_failures.append(
            {
                "ruleId": str(rule.id),
                "ruleName": rule.name,
                "planTier": rule.plan_tier,
                "orgId": str(rule.org_id) if rule.org_id else None,
                "userId": str(rule.user_id) if rule.user_id else None,
                "channels": [dict(entry) for entry in failures],
            }
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "evaluated": self.evaluated,
            "triggered": self.triggered,
            "skipped": self.skipped,
            "errors": self.errors,
            "duplicates": self.duplicates,
            "by_plan": {plan: vars(stats).copy() for plan, stats in self.by_plan.items()},
            "channelFailures": [dict(entry) for entry in self.channel_failures],
        }


def _load_worker_state(rule: AlertRule) -> Mapping[str, Any]:
    extras = rule.extras or {}
    state = extras.get(_EVAL_STATE_KEY, {})
    return state if isinstance(state, dict) else {}


def _persist_worker_state(rule: AlertRule, snapshot: _RuleSnapshot, *, duplicate: bool) -> None:
    extras = dict(rule.extras or {})
    payload = snapshot.as_dict()
    payload["version"] = _EVAL_STATE_VERSION
    payload["duplicateBlocked"] = bool(duplicate)
    extras[_EVAL_STATE_KEY] = payload
    rule.extras = extras
    rule.state = payload


def _is_duplicate_snapshot(state: Mapping[str, Any], snapshot: _RuleSnapshot) -> bool:
    if not snapshot.has_events:
        return False
    return (
        state.get("planSignature") == snapshot.plan_signature
        and state.get("eventHash") == snapshot.event_hash
    )


def _event_identity(event: Mapping[str, Any]) -> str:
    for key in ("id", "url", "ticker", "corp_name", "headline"):
        value = event.get(key)
        if value:
            return str(value)
    return snapshot_digest([event])


def _build_snapshot(
    plan: CompiledRulePlan,
    events_json: List[Dict[str, Any]],
    window_start: datetime,
    evaluated_at: datetime,
) -> _RuleSnapshot:
    identifiers = tuple(
        _event_identity(event)
        for event in events_json[:_MAX_STATE_EVENT_IDS]
    )
    digest = snapshot_digest(events_json)
    signature = plan_signature(plan)
    return _RuleSnapshot(
        plan_signature=signature,
        event_hash=digest,
        event_ids=identifiers,
        event_count=len(events_json),
        window_minutes=plan.window_minutes,
        window_start=window_start,
        evaluated_at=evaluated_at,
    )


def evaluate_due_alerts(
    db: Session,
    *,
    now: Optional[datetime] = None,
    limit: int = 100,
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate alert rules that are due and dispatch notifications."""
    now = now or _now_utc()
    limit = max(limit, 1)
    rules = _fetch_active_rules(db, limit)
    stats = _EvaluationAccumulator()

    for rule in rules:
        _process_rule(db, rule, now, task_id, stats)

    return stats.as_dict()


def _fetch_active_rules(db: Session, limit: int) -> List[AlertRule]:
    return (
        db.query(AlertRule)
        .filter(AlertRule.status == "active")
        .order_by(AlertRule.updated_at.asc())
        .limit(limit)
        .all()
    )


def _process_rule(
    db: Session,
    rule: AlertRule,
    now: datetime,
    task_id: Optional[str],
    stats: _EvaluationAccumulator,
) -> None:
    stats.record_evaluated(rule.plan_tier)
    outcome = "evaluated"
    timer_start = time.perf_counter()

    try:
        if _rule_is_throttled(rule, now):
            stats.record_skipped(rule.plan_tier)
            _audit_cooldown_block(rule)
            outcome = "cooldown"
            return

        if _rule_not_due(rule, now):
            stats.record_skipped(rule.plan_tier)
            outcome = "not_due"
            return

        if not _apply_daily_cap(db, rule, now):
            logger.info("Daily cap reached for alert %s", rule.id)
            stats.record_skipped(rule.plan_tier)
            outcome = "daily_cap"
            return

        try:
            evaluation = _evaluate_rule(db, rule, now)
            rule.last_evaluated_at = now
        except Exception as exc:  # pragma: no cover - defensive guard
            stats.record_error(rule.plan_tier)
            current_errors = int(rule.error_count or 0) + 1
            rule.error_count = current_errors
            backoff_minutes = _error_backoff_minutes(current_errors)
            if backoff_minutes:
                rule.cooled_until = now + timedelta(minutes=backoff_minutes)
            logger.error(
                "Alert evaluation error (rule=%s plan=%s task=%s retries=%s): %s",
                rule.id,
                rule.plan_tier,
                task_id,
                current_errors,
                exc,
                exc_info=True,
            )
            outcome = "error"
            return

        snapshot = evaluation.snapshot
        state = _load_worker_state(rule)

        if not evaluation.matches:
            _persist_worker_state(rule, snapshot, duplicate=False)
            outcome = "no_match"
            return

        if _is_duplicate_snapshot(state, snapshot):
            stats.record_duplicate(rule.plan_tier)
            _persist_worker_state(rule, snapshot, duplicate=True)
            alert_metrics.record_duplicate(rule.plan_tier, cause="snapshot")
            outcome = "duplicate"
            return

        stats.record_triggered(rule.plan_tier)
        rule.last_triggered_at = now

        cooldown = max(rule.cooldown_minutes or 0, 0)
        if cooldown:
            rule.cooled_until = now + timedelta(minutes=cooldown)

        first_event = evaluation.events_json[0] if evaluation.events_json else None
        channel_failures, failure_details = _dispatch_rule_notifications(
            db,
            rule,
            evaluation.message,
            evaluation.events_json,
            trigger_signature=snapshot.plan_signature,
            event_reference=first_event,
        )
        if channel_failures:
            rule.error_count = min(int(rule.error_count or 0) + channel_failures, 1000)
            stats.record_channel_failure(rule, failure_details)
            logger.warning(
                "Alert delivery failures (rule=%s failed_channels=%s task=%s)",
                rule.id,
                channel_failures,
                task_id,
            )
            outcome = "delivery_error"
        else:
            rule.error_count = 0
            outcome = "triggered"
        _persist_worker_state(rule, snapshot, duplicate=False)
    finally:
        duration = max(time.perf_counter() - timer_start, 0.0)
        alert_metrics.observe_rule_latency(rule.plan_tier, outcome, duration)


def _dispatch_rule_notifications(
    db: Session,
    rule: AlertRule,
    message: str,
    events_json: List[Dict[str, Any]],
    *,
    trigger_signature: Optional[str] = None,
    event_reference: Optional[Mapping[str, Any]] = None,
) -> Tuple[int, List[Dict[str, Any]]]:
    channel_failures = 0
    failure_state = dict(rule.channel_failures or {})
    state_changed = False
    now = _now_utc()
    for channel_type in list(failure_state.keys()):
        entry = failure_state[channel_type]
        retry_at = _parse_iso_datetime(entry.get("retryAfter") if isinstance(entry, Mapping) else None)
        if retry_at and retry_at > now:
            continue
        failure_state.pop(channel_type, None)
        state_changed = True
    reference_event = event_reference if isinstance(event_reference, Mapping) else (events_json[0] if events_json else None)
    failure_details: List[Dict[str, Any]] = []
    for channel in rule.channels:
        channel_type = str(channel.get("type", "")).lower().strip()
        cooldown_until = _channel_cooldown_until(failure_state, channel_type, now)
        if cooldown_until:
            reason = f"채널 {channel_type} 재시도 대기중 ({cooldown_until.isoformat()} 이후 가능)"
            throttled_result = NotificationResult(
                status="throttled",
                error=reason,
                delivered=0,
                failed=0,
                metadata={"retryAfter": cooldown_until.isoformat()},
            )
            _record_delivery(
                db,
                rule=rule,
                channel=channel,
                status="throttled",
                message=message,
                events=events_json,
                error_message=reason,
                delivery=throttled_result,
                event_ref=reference_event,
                trigger_hash=trigger_signature,
            )
            channel_failures += 1
            continue

        result = _send_via_channel(channel, message)
        _record_delivery(
            db,
            rule=rule,
            channel=channel,
            status=result.status,
            message=message,
            events=events_json,
            error_message=result.error,
            delivery=result,
            event_ref=reference_event,
            trigger_hash=trigger_signature,
        )
        if result.status != "delivered":
            channel_failures += 1
            retry_after = (now + timedelta(minutes=ALERT_CHANNEL_FAILURE_COOLDOWN_MINUTES)).isoformat()
            failure_state[channel_type] = {
                "status": result.status,
                "error": result.error,
                "updatedAt": now.isoformat(),
                "retryAfter": retry_after,
                "cooldownMinutes": ALERT_CHANNEL_FAILURE_COOLDOWN_MINUTES,
            }
            failure_details.append(
                {
                    "channel": channel_type,
                    "status": result.status,
                    "error": result.error,
                    "retryAfter": retry_after,
                    "target": channel.get("target"),
                    "targets": channel.get("targets"),
                }
            )
            state_changed = True
        elif channel_type in failure_state:
            failure_state.pop(channel_type, None)
            state_changed = True
    if state_changed:
        rule.channel_failures = failure_state
    return channel_failures, failure_details


def _rule_is_throttled(rule: AlertRule, now: datetime) -> bool:
    return bool(rule.cooled_until and rule.cooled_until > now)


def _audit_cooldown_block(rule: AlertRule) -> None:
    if not ALERTS_ENABLE_MODEL or not rule.cooled_until:
        return
    try:
        audit_alert_event(
            action="alerts.cooldown_blocked",
            user_id=rule.user_id,
            org_id=rule.org_id,
            target_id=str(rule.id),
            extra={
                "planTier": rule.plan_tier,
                "cooledUntil": rule.cooled_until.isoformat(),
                "cooldownMinutes": rule.cooldown_minutes,
            },
        )
    except Exception:  # pragma: no cover - audit logging best effort
        logger.debug("Failed to record cooldown audit for rule=%s", rule.id, exc_info=True)


def _rule_not_due(rule: AlertRule, now: datetime) -> bool:
    if not rule.last_evaluated_at:
        return False
    interval = max(rule.evaluation_interval_minutes or 1, 1)
    due_at = rule.last_evaluated_at + timedelta(minutes=interval)
    return due_at > now


def _evaluate_rule(
    db: Session,
    rule: AlertRule,
    now: datetime,
) -> _RuleEvaluationResult:
    condition = rule.condition or {}
    plan = compile_trigger(
        condition,
        default_window_minutes=rule.window_minutes,
        default_source=str(condition.get("type") or "filing").lower(),
    )
    event_type = plan.source if plan.source in {"news", "filing"} else "filing"
    window_start = _window_start(rule, now, override_minutes=plan.window_minutes)

    if event_type == "news":
        events: Sequence[Any] = _query_news(
            db,
            tickers=plan.tickers,
            sectors=plan.sectors,
            keywords=plan.keywords,
            entities=plan.entities,
            min_sentiment=plan.min_sentiment,
            since=window_start,
        )
    else:
        events = _query_filings(
            db,
            tickers=plan.tickers,
            categories=plan.categories,
            keywords=plan.keywords,
            entities=plan.entities,
            since=window_start,
        )

    events_list = list(events)
    events_json = _build_event_context(events_list, event_type)
    message = _render_message(rule, events_list, event_type) if events_list else DEFAULT_MESSAGE
    snapshot = _build_snapshot(plan, events_json, window_start, now)

    return _RuleEvaluationResult(
        plan=plan,
        event_type=event_type,
        events=events_list,
        events_json=events_json,
        message=message,
        matches=bool(events_list),
        window_start=window_start,
        snapshot=snapshot,
    )


def _serialize_frequency(rule: AlertRule) -> Dict[str, Optional[int]]:
    return {
        "evaluationIntervalMinutes": rule.evaluation_interval_minutes,
        "windowMinutes": rule.window_minutes,
        "cooldownMinutes": rule.cooldown_minutes,
        "maxTriggersPerDay": rule.max_triggers_per_day,
    }


def serialize_alert(rule: AlertRule) -> Dict[str, Any]:
    frequency_payload = _serialize_frequency(rule)
    return {
        "id": str(rule.id),
        "name": rule.name,
        "description": rule.description,
        "planTier": rule.plan_tier,
        "status": rule.status,
        "trigger": rule.trigger,
        "condition": rule.trigger,
        "triggerType": rule.trigger_type,
        "filters": rule.filters or {},
        "state": rule.state or {},
        "channelFailures": rule.channel_failures or {},
        "channels": rule.channels,
        "frequency": frequency_payload,
        "messageTemplate": rule.message_template,
        "evaluationIntervalMinutes": frequency_payload["evaluationIntervalMinutes"],
        "windowMinutes": frequency_payload["windowMinutes"],
        "cooldownMinutes": frequency_payload["cooldownMinutes"],
        "maxTriggersPerDay": frequency_payload["maxTriggersPerDay"],
        "lastTriggeredAt": rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
        "lastEvaluatedAt": rule.last_evaluated_at.isoformat() if rule.last_evaluated_at else None,
        "cooledUntil": rule.cooled_until.isoformat() if rule.cooled_until else None,
        "throttleUntil": rule.cooled_until.isoformat() if rule.cooled_until else None,
        "errorCount": rule.error_count,
        "extras": rule.extras,
        "createdAt": rule.created_at.isoformat() if rule.created_at else None,
        "updatedAt": rule.updated_at.isoformat() if rule.updated_at else None,
    }


def rule_delivery_stats(
    db: Session,
    rule_id: uuid.UUID,
    *,
    window_minutes: Optional[int] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Aggregate delivery stats for a rule."""
    now = now or _now_utc()
    query = db.query(AlertDelivery).filter(AlertDelivery.alert_id == rule_id)
    window_start: Optional[datetime] = None
    if window_minutes and window_minutes > 0:
        window_start = now - timedelta(minutes=window_minutes)
        query = query.filter(AlertDelivery.created_at >= window_start)

    aggregates = (
        db.query(
            func.count(AlertDelivery.id).label("total"),
            func.coalesce(func.sum(case((AlertDelivery.status == "delivered", 1), else_=0)), 0).label("delivered"),
            func.coalesce(func.sum(case((AlertDelivery.status == "failed", 1), else_=0)), 0).label("failed"),
            func.coalesce(func.sum(case((AlertDelivery.status == "throttled", 1), else_=0)), 0).label("throttled"),
        )
        .filter(AlertDelivery.alert_id == rule_id)
    )
    if window_start:
        aggregates = aggregates.filter(AlertDelivery.created_at >= window_start)
    agg_row = aggregates.one()

    last_delivery = (
        db.query(AlertDelivery)
        .filter(AlertDelivery.alert_id == rule_id)
        .order_by(AlertDelivery.created_at.desc())
        .first()
    )

    return {
        "ruleId": str(rule_id),
        "windowMinutes": window_minutes,
        "total": int(agg_row.total or 0),
        "delivered": int(agg_row.delivered or 0),
        "failed": int(agg_row.failed or 0),
        "throttled": int(agg_row.throttled or 0),
        "lastDelivery": {
            "id": str(last_delivery.id),
            "status": last_delivery.status,
            "channel": last_delivery.channel,
            "error": last_delivery.error_message,
            "createdAt": last_delivery.created_at.isoformat() if last_delivery.created_at else None,
        }
        if last_delivery
        else None,
    }


def list_event_alert_matches(
    db: Session,
    *,
    owner_filters: Mapping[str, Optional[Any]],
    limit: int,
    since: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    query = (
        db.query(EventAlertMatch, EventRecord, AlertRule)
        .join(AlertRule, EventAlertMatch.alert_id == AlertRule.id)
        .join(EventRecord, EventAlertMatch.event_id == EventRecord.rcept_no)
    )
    for column, value in owner_filters.items():
        if value is None:
            query = query.filter(getattr(AlertRule, column).is_(None))
        else:
            query = query.filter(getattr(AlertRule, column) == value)

    if since:
        query = query.filter(EventAlertMatch.matched_at >= since)

    rows = (
        query.order_by(EventAlertMatch.matched_at.desc())
        .limit(max(1, min(limit, 200)))
        .all()
    )

    matches: List[Dict[str, Any]] = []
    for match_row, event_row, rule_row in rows:
        matches.append(
            {
                "eventId": match_row.event_id,
                "alertId": str(match_row.alert_id),
                "ruleName": rule_row.name,
                "eventType": event_row.event_type,
                "ticker": event_row.ticker,
                "corpName": event_row.corp_name,
                "eventDate": event_row.event_date.isoformat() if event_row.event_date else None,
                "matchScore": float(match_row.match_score) if match_row.match_score is not None else None,
                "matchedAt": match_row.matched_at.isoformat() if match_row.matched_at else None,
                "domain": event_row.domain,
                "subtype": event_row.subtype,
                "metadata": match_row.metadata or {},
            }
        )
    return matches


def serialize_plan_capabilities(
    plan_tier: str,
    rules: Sequence[AlertRule],
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    now = now or _now_utc()
    config = _plan_config(plan_tier)
    non_archived = [rule for rule in rules if rule.status != "archived"]
    max_alerts = int(config["max_alerts"])
    remaining = max(0, max_alerts - len(non_archived)) if max_alerts else 0
    next_eval = _next_evaluation_at(non_archived, now)
    return {
        "planTier": plan_tier,
        "maxAlerts": max_alerts,
        "remainingAlerts": remaining,
        "channels": list(config["channels"]),
        "maxDailyTriggers": config.get("max_daily_triggers"),
        "defaultEvaluationIntervalMinutes": config.get("default_evaluation_interval_minutes"),
        "defaultWindowMinutes": config.get("default_window_minutes"),
        "defaultCooldownMinutes": config.get("default_cooldown_minutes"),
        "minEvaluationIntervalMinutes": config.get("min_evaluation_interval_minutes"),
        "minCooldownMinutes": config.get("min_cooldown_minutes"),
        "frequencyDefaults": {
            "evaluationIntervalMinutes": config.get("default_evaluation_interval_minutes"),
            "windowMinutes": config.get("default_window_minutes"),
            "cooldownMinutes": config.get("default_cooldown_minutes"),
            "maxTriggersPerDay": config.get("max_daily_triggers"),
        },
        "nextEvaluationAt": next_eval.isoformat() if next_eval else None,
    }


def _apply_plan_frequency(plan_tier: str, frequency: Mapping[str, Any]) -> Dict[str, Optional[int]]:
    config = _plan_config(plan_tier)
    payload = frequency or {}

    def _coerce_int(key: str, default: int, *, minimum: Optional[int] = None) -> int:
        value = payload.get(key)
        try:
            candidate = int(value)
        except (TypeError, ValueError):
            candidate = default
        if minimum is not None:
            candidate = max(candidate, minimum)
        return candidate

    eval_default = int(config["default_evaluation_interval_minutes"])
    eval_min = int(config["min_evaluation_interval_minutes"])
    evaluation_interval = _coerce_int("evaluationIntervalMinutes", eval_default, minimum=eval_min)

    window_default = int(config["default_window_minutes"])
    window_min = max(5, evaluation_interval)
    window_minutes = _coerce_int("windowMinutes", window_default, minimum=window_min)

    cooldown_default = int(config["default_cooldown_minutes"])
    cooldown_min = int(config["min_cooldown_minutes"])
    cooldown_minutes = _coerce_int("cooldownMinutes", cooldown_default, minimum=cooldown_min)

    plan_daily_cap = config.get("max_daily_triggers")
    max_triggers_raw = payload.get("maxTriggersPerDay")
    if plan_daily_cap:
        plan_cap_int = int(plan_daily_cap)
        if max_triggers_raw in (None, "", 0):
            max_triggers_per_day: Optional[int] = plan_cap_int
        else:
            try:
                candidate = int(max_triggers_raw)
            except (TypeError, ValueError):
                candidate = plan_cap_int
            max_triggers_per_day = min(max(candidate, 1), plan_cap_int)
    else:
        if max_triggers_raw in (None, "", 0):
            max_triggers_per_day = None
        else:
            try:
                candidate = int(max_triggers_raw)
            except (TypeError, ValueError):
                candidate = None
            max_triggers_per_day = max(candidate, 1) if candidate else None

    return {
        "evaluationIntervalMinutes": evaluation_interval,
        "windowMinutes": window_minutes,
        "cooldownMinutes": cooldown_minutes,
        "maxTriggersPerDay": max_triggers_per_day,
    }


def _next_evaluation_at(rules: Sequence[AlertRule], now: datetime) -> Optional[datetime]:
    due_times: List[datetime] = []
    for rule in rules:
        if rule.status != "active":
            continue
        if rule.cooled_until and rule.cooled_until > now:
            due_times.append(rule.cooled_until)
            continue
        interval = max(rule.evaluation_interval_minutes or 1, 1)
        if rule.last_evaluated_at:
            due_at = rule.last_evaluated_at + timedelta(minutes=interval)
            if due_at > now:
                due_times.append(due_at)
            else:
                due_times.append(now)
        else:
            due_times.append(now)
    if not due_times:
        return None
    return min(due_times)
