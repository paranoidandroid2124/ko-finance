"""Business logic for alert rule management and dispatch."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from dataclasses import dataclass, field

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from models.alert import AlertDelivery, AlertRule
from models.filing import Filing
from models.news import NewsSignal
from services.notification_service import NotificationResult, dispatch_notification
from services.alert_channel_registry import validate_channel_payload

logger = logging.getLogger(__name__)

ERROR_BACKOFF_SEQUENCE = (5, 15, 60)
PLAN_CONSTRAINTS: Dict[str, Dict[str, Any]] = {
    "free": {
        "max_alerts": 0,
        "channels": (),
        "default_evaluation_interval_minutes": 60,
        "default_window_minutes": 1440,
        "default_cooldown_minutes": 1440,
        "min_cooldown_minutes": 0,
        "min_evaluation_interval_minutes": 1,
        "max_daily_triggers": 0,
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

DEFAULT_MESSAGE = "새로운 알림이 감지되었습니다."


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
    condition: Dict[str, Any],
    channels: Sequence[Dict[str, Any]],
    message_template: Optional[str],
    evaluation_interval_minutes: int,
    window_minutes: int,
    cooldown_minutes: int,
    max_triggers_per_day: Optional[int],
    extras: Optional[Dict[str, Any]] = None,
) -> AlertRule:
    plan_tier = _normalize_plan_tier(plan_tier)
    ensure_plan_allows_creation(db, plan_tier=plan_tier, owner_filters=owner_filters)
    normalized_channels = validate_channels(plan_tier, channels)
    evaluation_interval_minutes, window_minutes, cooldown_minutes, max_triggers_per_day = _apply_plan_defaults(
        plan_tier,
        evaluation_interval_minutes,
        window_minutes,
        cooldown_minutes,
        max_triggers_per_day,
    )

    rule = AlertRule(
        plan_tier=plan_tier,
        name=name.strip(),
        description=description.strip() if description else None,
        condition=condition or {},
        channels=normalized_channels,
        message_template=message_template.strip() if message_template else None,
        evaluation_interval_minutes=evaluation_interval_minutes,
        window_minutes=window_minutes,
        cooldown_minutes=cooldown_minutes,
        max_triggers_per_day=max_triggers_per_day,
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
    if "name" in changes and changes["name"]:
        rule.name = str(changes["name"]).strip()
    if "description" in changes:
        description = changes["description"]
        rule.description = description.strip() if description else None
    if "condition" in changes and changes["condition"]:
        rule.condition = changes["condition"]
    if "channels" in changes and changes["channels"] is not None:
        rule.channels = validate_channels(plan_tier, changes["channels"])
    if "message_template" in changes:
        message = changes["message_template"]
        rule.message_template = message.strip() if message else None
    if "status" in changes and changes["status"] in {"active", "paused", "archived"}:
        rule.status = changes["status"]
    if any(
        key in changes
        for key in ("evaluation_interval_minutes", "window_minutes", "cooldown_minutes", "max_triggers_per_day")
    ):
        evaluation_interval_minutes = changes.get("evaluation_interval_minutes", rule.evaluation_interval_minutes)
        window_minutes = changes.get("window_minutes", rule.window_minutes)
        cooldown_minutes = changes.get("cooldown_minutes", rule.cooldown_minutes)
        max_triggers_per_day = changes.get("max_triggers_per_day", rule.max_triggers_per_day)
        (
            rule.evaluation_interval_minutes,
            rule.window_minutes,
            rule.cooldown_minutes,
            rule.max_triggers_per_day,
        ) = _apply_plan_defaults(
            plan_tier,
            evaluation_interval_minutes,
            window_minutes,
            cooldown_minutes,
            max_triggers_per_day,
        )
    if "extras" in changes and isinstance(changes["extras"], dict):
        rule.extras = {**rule.extras, **changes["extras"]}
    return rule


def archive_alert_rule(db: Session, *, rule: AlertRule) -> None:
    rule.status = "archived"


def _window_start(rule: AlertRule, now: datetime) -> datetime:
    window = max(rule.window_minutes or 60, 5)
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
    since: datetime,
) -> List[Filing]:
    since_naive = since.replace(tzinfo=None)
    query = db.query(Filing).filter(Filing.filed_at.isnot(None))
    query = query.filter(Filing.filed_at >= since_naive)
    if tickers:
        query = query.filter(Filing.ticker.in_(tickers))
    if categories:
        query = query.filter(Filing.category.in_(categories))
    query = query.order_by(Filing.filed_at.desc())
    return list(query.limit(10).all())


def _query_news(
    db: Session,
    *,
    tickers: Sequence[str],
    sectors: Sequence[str],
    min_sentiment: Optional[float],
    since: datetime,
) -> List[NewsSignal]:
    query = db.query(NewsSignal).filter(NewsSignal.published_at >= since)
    if tickers:
        query = query.filter(NewsSignal.ticker.in_(tickers))
    if sectors:
        query = query.filter(or_(NewsSignal.sector.in_(sectors), NewsSignal.industry.in_(sectors)))
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
    )
    db.add(record)
    return record


@dataclass
class _PlanEvaluationStats:
    evaluated: int = 0
    triggered: int = 0
    skipped: int = 0
    errors: int = 0


@dataclass
class _EvaluationAccumulator:
    evaluated: int = 0
    triggered: int = 0
    skipped: int = 0
    errors: int = 0
    by_plan: Dict[str, _PlanEvaluationStats] = field(default_factory=dict)

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

    def as_dict(self) -> Dict[str, Any]:
        return {
            "evaluated": self.evaluated,
            "triggered": self.triggered,
            "skipped": self.skipped,
            "errors": self.errors,
            "by_plan": {plan: vars(stats).copy() for plan, stats in self.by_plan.items()},
        }


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

    if _rule_is_throttled(rule, now) or _rule_not_due(rule, now):
        stats.record_skipped(rule.plan_tier)
        return

    if not _apply_daily_cap(db, rule, now):
        logger.info("Daily cap reached for alert %s", rule.id)
        stats.record_skipped(rule.plan_tier)
        return

    try:
        matches, message, events_json = _evaluate_rule(db, rule, now)
        rule.last_evaluated_at = now
    except Exception as exc:  # pragma: no cover - defensive guard
        stats.record_error(rule.plan_tier)
        current_errors = int(rule.error_count or 0) + 1
        rule.error_count = current_errors
        backoff_minutes = _error_backoff_minutes(current_errors)
        if backoff_minutes:
            rule.throttle_until = now + timedelta(minutes=backoff_minutes)
        logger.error(
            "Alert evaluation error (rule=%s plan=%s task=%s retries=%s): %s",
            rule.id,
            rule.plan_tier,
            task_id,
            current_errors,
            exc,
            exc_info=True,
        )
        return

    if not matches:
        return

    stats.record_triggered(rule.plan_tier)
    rule.last_triggered_at = now

    cooldown = max(rule.cooldown_minutes or 0, 0)
    if cooldown:
        rule.throttle_until = now + timedelta(minutes=cooldown)

    channel_failures = _dispatch_rule_notifications(db, rule, message, events_json)
    if channel_failures:
        rule.error_count = min(int(rule.error_count or 0) + channel_failures, 1000)
        logger.warning(
            "Alert delivery failures (rule=%s failed_channels=%s task=%s)",
            rule.id,
            channel_failures,
            task_id,
        )
    else:
        rule.error_count = 0


def _dispatch_rule_notifications(
    db: Session,
    rule: AlertRule,
    message: str,
    events_json: List[Dict[str, Any]],
) -> int:
    channel_failures = 0
    for channel in rule.channels:
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
        )
        if result.status != "delivered":
            channel_failures += 1
    return channel_failures


def _rule_is_throttled(rule: AlertRule, now: datetime) -> bool:
    return bool(rule.throttle_until and rule.throttle_until > now)


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
) -> Tuple[bool, str, List[Dict[str, Any]]]:
    condition = rule.condition or {}
    event_type = str(condition.get("type") or "filing").lower()
    window_start = _window_start(rule, now)
    tickers = condition.get("tickers") or []

    events: Sequence[Any]
    if event_type == "news":
        sectors = condition.get("sectors") or []
        min_sentiment = condition.get("minSentiment")
        events = _query_news(
            db,
            tickers=tickers,
            sectors=sectors,
            min_sentiment=min_sentiment,
            since=window_start,
        )
    else:
        categories = condition.get("categories") or []
        events = _query_filings(
            db,
            tickers=tickers,
            categories=categories,
            since=window_start,
        )

    if not events:
        return False, DEFAULT_MESSAGE, []

    events_json = _build_event_context(events, event_type)
    message = _render_message(rule, events, event_type)
    return True, message, events_json


def serialize_alert(rule: AlertRule) -> Dict[str, Any]:
    return {
        "id": str(rule.id),
        "name": rule.name,
        "description": rule.description,
        "planTier": rule.plan_tier,
        "status": rule.status,
        "condition": rule.condition,
        "channels": rule.channels,
        "messageTemplate": rule.message_template,
        "evaluationIntervalMinutes": rule.evaluation_interval_minutes,
        "windowMinutes": rule.window_minutes,
        "cooldownMinutes": rule.cooldown_minutes,
        "maxTriggersPerDay": rule.max_triggers_per_day,
        "lastTriggeredAt": rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
        "lastEvaluatedAt": rule.last_evaluated_at.isoformat() if rule.last_evaluated_at else None,
        "throttleUntil": rule.throttle_until.isoformat() if rule.throttle_until else None,
        "errorCount": rule.error_count,
        "extras": rule.extras,
        "createdAt": rule.created_at.isoformat() if rule.created_at else None,
        "updatedAt": rule.updated_at.isoformat() if rule.updated_at else None,
    }


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
        "nextEvaluationAt": next_eval.isoformat() if next_eval else None,
    }


def _apply_plan_defaults(
    plan_tier: str,
    evaluation_interval_minutes: Optional[int],
    window_minutes: Optional[int],
    cooldown_minutes: Optional[int],
    max_triggers_per_day: Optional[int],
) -> Tuple[int, int, int, Optional[int]]:
    config = _plan_config(plan_tier)
    eval_default = int(config["default_evaluation_interval_minutes"])
    eval_min = int(config["min_evaluation_interval_minutes"])
    window_default = int(config["default_window_minutes"])
    cooldown_default = int(config["default_cooldown_minutes"])
    cooldown_min = int(config["min_cooldown_minutes"])
    plan_daily_cap = config.get("max_daily_triggers")

    evaluation_interval = int(evaluation_interval_minutes or eval_default)
    evaluation_interval = max(evaluation_interval, eval_min)

    window = int(window_minutes or window_default)
    window = max(window, max(5, evaluation_interval))

    cooldown = int(cooldown_minutes if cooldown_minutes is not None else cooldown_default)
    cooldown = max(cooldown, cooldown_min)

    if plan_daily_cap:
        if max_triggers_per_day is None:
            daily_cap: Optional[int] = int(plan_daily_cap)
        else:
            daily_cap = min(int(max_triggers_per_day), int(plan_daily_cap))
    else:
        daily_cap = int(max_triggers_per_day) if max_triggers_per_day is not None else None

    return evaluation_interval, window, cooldown, daily_cap


def _next_evaluation_at(rules: Sequence[AlertRule], now: datetime) -> Optional[datetime]:
    due_times: List[datetime] = []
    for rule in rules:
        if rule.status != "active":
            continue
        if rule.throttle_until and rule.throttle_until > now:
            due_times.append(rule.throttle_until)
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
