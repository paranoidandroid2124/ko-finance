from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from core.env import env_int
from core.logging import get_logger
from database import get_db
from schemas.api.alerts import (
    AlertChannelSchemaResponse,
    AlertEventMatchResponse,
    AlertRuleCreateRequest,
    AlertRuleListResponse,
    AlertRuleResponse,
    AlertRuleUpdateRequest,
    AlertRuleStatsResponse,
    AlertPlanInfo,
    WatchlistDispatchRequest,
    WatchlistDispatchResponse,
    WatchlistRadarResponse,
    WatchlistRuleDetailResponse,
)
from services.alert_service import (
    PlanQuotaError,
    allowed_channels,
    create_alert_rule,
    get_alert_rule,
    list_alert_rules,
    list_event_alert_matches,
    rule_delivery_stats,
    serialize_alert,
    serialize_plan_capabilities,
    update_alert_rule,
    archive_alert_rule,
)
from services.alert_channel_registry import list_channel_definitions
from services import alert_rate_limiter, watchlist_service
from services.audit_log import audit_alert_event
from services.user_settings_service import UserLightMemSettings
from services import lightmem_gate
from services.plan_service import PlanContext
from web.deps import require_plan_feature
from web.quota_guard import enforce_quota

router = APIRouter(prefix="/alerts", tags=["Alerts"])
logger = get_logger(__name__)

ALERTS_WRITE_RATE_LIMIT = env_int("ALERTS_WRITE_RATE_LIMIT", 30, minimum=1)
ALERTS_WRITE_RATE_WINDOW_SECONDS = env_int("ALERTS_WRITE_RATE_WINDOW_SECONDS", 900, minimum=60)


def _parse_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="잘못된 UUID 형식입니다.")


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "alerts.invalid_window", "message": "잘못된 시간 형식입니다."},
        ) from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _normalize_query_list(values: Optional[List[str]]) -> List[str]:
    normalized: List[str] = []
    if not values:
        return normalized
    for raw in values:
        if not isinstance(raw, str):
            continue
        for part in raw.split(","):
            trimmed = part.strip()
            if trimmed and trimmed not in normalized:
                normalized.append(trimmed)
    return normalized


def _default_lightmem_user_id() -> Optional[uuid.UUID]:
    return lightmem_gate.default_user_id()


def _resolve_lightmem_user_id(value: Optional[str]) -> Optional[uuid.UUID]:
    if value:
        return _parse_uuid(value)
    return _default_lightmem_user_id()


def _load_user_lightmem_settings(
    user_id: Optional[uuid.UUID],
) -> Optional[UserLightMemSettings]:
    return lightmem_gate.load_user_settings(user_id)


def _watchlist_memory_enabled(
    plan: PlanContext,
    user_settings: Optional[UserLightMemSettings],
) -> bool:
    return lightmem_gate.watchlist_enabled(plan, user_settings)


def _owner_filters(user_id: Optional[uuid.UUID], org_id: Optional[uuid.UUID]) -> dict:
    return {"user_id": user_id, "org_id": org_id}


def _rate_limit_identifier(user_id: Optional[uuid.UUID], org_id: Optional[uuid.UUID]) -> str:
    if org_id:
        return str(org_id)
    if user_id:
        return str(user_id)
    return "anonymous"


def _enforce_write_rate_limit(user_id: Optional[uuid.UUID], org_id: Optional[uuid.UUID]) -> None:
    if ALERTS_WRITE_RATE_LIMIT <= 0:
        return
    result = alert_rate_limiter.check_limit(
        scope="alerts.write",
        identifier=_rate_limit_identifier(user_id, org_id),
        limit=ALERTS_WRITE_RATE_LIMIT,
        window_seconds=ALERTS_WRITE_RATE_WINDOW_SECONDS,
    )
    if result.allowed:
        return
    detail = {
        "code": "alerts.rate_limited",
        "message": "알림 설정 요청이 현재 제한되어 있습니다.",
    }
    if result.reset_at:
        detail["resetAt"] = result.reset_at.isoformat()
    raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)


def _audit_rule_event(
    action: str,
    rule,
    user_id: Optional[uuid.UUID],
    org_id: Optional[uuid.UUID],
) -> None:
    if rule is None:
        target_id = None
        plan_tier = None
        status_value = None
    else:
        target_id = str(getattr(rule, "id", None))
        plan_tier = getattr(rule, "plan_tier", None)
        status_value = getattr(rule, "status", None)
    try:
        audit_alert_event(
            action=action,
            user_id=user_id,
            org_id=org_id,
            target_id=target_id,
            extra={"planTier": plan_tier, "status": status_value},
        )
    except Exception:  # pragma: no cover - audit logging best effort
        logger.debug("Failed to record audit event=%s target=%s", action, target_id, exc_info=True)


def _response_from_rule(rule) -> AlertRuleResponse:
    payload = serialize_alert(rule)
    return AlertRuleResponse.model_validate(payload)


def _plan_http_exception(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


@router.get("", response_model=AlertRuleListResponse)
def list_rules(
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
    plan: PlanContext = Depends(require_plan_feature("search.alerts")),
) -> AlertRuleListResponse:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    rules = list_alert_rules(db, owner_filters=_owner_filters(user_id, org_id))
    items = [_response_from_rule(rule) for rule in rules]
    plan_info = AlertPlanInfo.model_validate(serialize_plan_capabilities(plan.tier, rules))
    return AlertRuleListResponse(items=items, plan=plan_info)


@router.post("", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(
    payload: AlertRuleCreateRequest,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
    plan: PlanContext = Depends(require_plan_feature("search.alerts")),
) -> AlertRuleResponse:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    filters = _owner_filters(user_id, org_id)
    enforce_quota("alerts.rules.create", plan=plan, user_id=user_id, org_id=org_id)
    _enforce_write_rate_limit(user_id, org_id)
    try:
        rule = create_alert_rule(
            db,
            plan_tier=plan.tier,
            owner_filters=filters,
            name=payload.name,
            description=payload.description,
            trigger=payload.trigger.model_dump(),
            channels=[channel.model_dump() for channel in payload.channels],
            message_template=payload.messageTemplate,
            frequency=payload.frequency.model_dump(),
            extras=payload.extras,
        )
        db.commit()
        _audit_rule_event("alerts.create", rule, user_id, org_id)
    except PlanQuotaError as exc:
        db.rollback()
        raise _plan_http_exception(status.HTTP_403_FORBIDDEN, exc.code, str(exc))
    except ValueError as exc:
        db.rollback()
        raise _plan_http_exception(status.HTTP_400_BAD_REQUEST, "alerts.invalid_payload", str(exc))
    db.refresh(rule)
    return _response_from_rule(rule)


@router.patch("/{alert_id}", response_model=AlertRuleResponse)
def update_rule(
    alert_id: uuid.UUID,
    payload: AlertRuleUpdateRequest,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
    plan: PlanContext = Depends(require_plan_feature("search.alerts")),
) -> AlertRuleResponse:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    filters = _owner_filters(user_id, org_id)
    _enforce_write_rate_limit(user_id, org_id)
    rule = get_alert_rule(db, rule_id=alert_id, owner_filters=filters)
    if rule is None:
        raise _plan_http_exception(status.HTTP_404_NOT_FOUND, "alerts.not_found", "알림을 찾을 수 없습니다.")
    changes = payload.model_dump(exclude_unset=True)
    if payload.trigger is not None:
        changes["trigger"] = payload.trigger.model_dump()
    elif payload.condition is not None:
        changes["condition"] = payload.condition.model_dump()
    if payload.frequency is not None:
        changes["frequency"] = payload.frequency.model_dump()
    if payload.channels is not None:
        changes["channels"] = [channel.model_dump() for channel in payload.channels]
    try:
        updated = update_alert_rule(db, rule=rule, plan_tier=plan.tier, changes=changes)
        db.commit()
        _audit_rule_event("alerts.update", updated, user_id, org_id)
    except PlanQuotaError as exc:
        db.rollback()
        raise _plan_http_exception(status.HTTP_403_FORBIDDEN, exc.code, str(exc))
    except ValueError as exc:
        db.rollback()
        raise _plan_http_exception(status.HTTP_400_BAD_REQUEST, "alerts.invalid_payload", str(exc))
    db.refresh(updated)
    return _response_from_rule(updated)


@router.get("/{alert_id}/stats", response_model=AlertRuleStatsResponse)
def read_rule_stats(
    alert_id: uuid.UUID,
    window_minutes: int = Query(1440, ge=5, le=7 * 24 * 60),
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
    plan: PlanContext = Depends(require_plan_feature("search.alerts")),
) -> AlertRuleStatsResponse:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    filters = _owner_filters(user_id, org_id)
    rule = get_alert_rule(db, rule_id=alert_id, owner_filters=filters)
    if rule is None:
        raise _plan_http_exception(status.HTTP_404_NOT_FOUND, "alerts.not_found", "알림을 찾을 수 없습니다.")
    stats_payload = rule_delivery_stats(db, rule_id=alert_id, window_minutes=window_minutes)
    stats_payload["windowMinutes"] = window_minutes
    return AlertRuleStatsResponse.model_validate(stats_payload)


@router.get("/watchlist/event-matches", response_model=AlertEventMatchResponse)
def list_event_matches(
    limit: int = Query(20, ge=1, le=100),
    since: Optional[str] = Query(default=None),
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
    plan: PlanContext = Depends(require_plan_feature("search.alerts")),
) -> AlertEventMatchResponse:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    filters = _owner_filters(user_id, org_id)
    since_dt = _parse_iso_datetime(since)
    matches = list_event_alert_matches(
        db,
        owner_filters=filters,
        limit=limit,
        since=since_dt,
    )
    return AlertEventMatchResponse(matches=matches)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    alert_id: uuid.UUID,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
    plan: PlanContext = Depends(require_plan_feature("search.alerts")),
) -> None:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    filters = _owner_filters(user_id, org_id)
    _enforce_write_rate_limit(user_id, org_id)
    rule = get_alert_rule(db, rule_id=alert_id, owner_filters=filters)
    if rule is None:
        return
    archive_alert_rule(db, rule=rule)
    db.commit()
    _audit_rule_event("alerts.delete", rule, user_id, org_id)


@router.get("/watchlist/radar", response_model=WatchlistRadarResponse)
def watchlist_radar(
    window_minutes: int = 1440,
    limit: int = 100,
    channels: Optional[List[str]] = Query(default=None, description="채널 필터 (중복 지정 가능)"),
    event_types: Optional[List[str]] = Query(default=None, description="이벤트 유형 필터 (filing/news)"),
    tickers: Optional[List[str]] = Query(default=None, description="티커 필터"),
    rule_tags: Optional[List[str]] = Query(default=None, description="룰 태그 필터"),
    min_sentiment: Optional[float] = Query(default=None, description="감성 최소값 (-1.0 ~ 1.0)"),
    max_sentiment: Optional[float] = Query(default=None, description="감성 최대값 (-1.0 ~ 1.0)"),
    query: Optional[str] = Query(default=None, description="메시지/룰/티커 검색어"),
    window_start: Optional[str] = Query(default=None, description="ISO8601 시작 시각"),
    window_end: Optional[str] = Query(default=None, description="ISO8601 종료 시각"),
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    plan: PlanContext = Depends(require_plan_feature("search.alerts")),
    db: Session = Depends(get_db),
) -> WatchlistRadarResponse:
    window_minutes = max(min(int(window_minutes or 1440), 7 * 24 * 60), 5)
    limit = max(min(int(limit or 100), 200), 1)
    user_id = _resolve_lightmem_user_id(x_user_id)
    org_id = _parse_uuid(x_org_id)
    enforce_quota("watchlist.radar", plan=plan, user_id=user_id, org_id=org_id)
    owner_filters = _owner_filters(user_id, org_id)
    tenant_token = str(org_id) if org_id else None
    user_token = str(user_id) if user_id else None
    session_key = f"watchlist:radar:{tenant_token or user_token or 'global'}"
    user_memory_settings = _load_user_lightmem_settings(user_id)
    plan_memory_enabled = _watchlist_memory_enabled(plan, user_memory_settings)
    parsed_channels = _normalize_query_list(channels)
    parsed_event_types = _normalize_query_list(event_types)
    parsed_tickers = _normalize_query_list(tickers)
    parsed_rule_tags = _normalize_query_list(rule_tags)
    start_dt = _parse_iso_datetime(window_start)
    end_dt = _parse_iso_datetime(window_end)
    comparison_end = end_dt or datetime.now(timezone.utc)
    comparison_start = start_dt or (comparison_end - timedelta(minutes=window_minutes))
    if (comparison_end - comparison_start).total_seconds() > 7 * 24 * 60 * 60:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "alerts.window_too_large", "message": "검색 구간은 최대 7일까지 지원합니다."},
        )
    payload = watchlist_service.collect_watchlist_alerts(
        db,
        window_minutes=window_minutes,
        limit=limit,
        channels=parsed_channels,
        event_types=parsed_event_types,
        tickers=parsed_tickers,
        rule_tags=parsed_rule_tags,
        min_sentiment=min_sentiment,
        max_sentiment=max_sentiment,
        query=query,
        window_start=start_dt,
        window_end=end_dt,
        owner_filters=owner_filters,
        plan_memory_enabled=plan_memory_enabled,
        session_id=session_key,
        tenant_id=tenant_token,
        user_id_hint=user_token,
    )
    return WatchlistRadarResponse.model_validate(payload)


@router.post("/watchlist/dispatch", response_model=WatchlistDispatchResponse)
def watchlist_dispatch(
    payload: WatchlistDispatchRequest,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    plan: PlanContext = Depends(require_plan_feature("search.alerts")),
    db: Session = Depends(get_db),
) -> WatchlistDispatchResponse:
    window_minutes = max(min(int(payload.windowMinutes or 1440), 7 * 24 * 60), 5)
    limit = max(min(int(payload.limit or 20), 200), 1)
    user_id = _resolve_lightmem_user_id(x_user_id)
    org_id = _parse_uuid(x_org_id)
    enforce_quota("watchlist.digest", plan=plan, user_id=user_id, org_id=org_id)
    owner_filters = _owner_filters(user_id, org_id)
    tenant_token = str(org_id) if org_id else None
    user_token = str(user_id) if user_id else None
    session_key = f"watchlist:dispatch:{tenant_token or user_token or 'global'}"
    user_memory_settings = _load_user_lightmem_settings(user_id)
    plan_memory_enabled = _watchlist_memory_enabled(plan, user_memory_settings)
    result = watchlist_service.dispatch_watchlist_digest(
        db,
        window_minutes=window_minutes,
        limit=limit,
        slack_targets=payload.slackTargets or [],
        email_targets=payload.emailTargets or [],
        owner_filters=owner_filters,
        plan_memory_enabled=plan_memory_enabled,
        session_id=session_key,
        tenant_id=tenant_token,
        user_id_hint=user_token,
    )
    summary_payload = result.get("payload", {}).get("summary") or {}
    response = WatchlistDispatchResponse.model_validate(
        {
            "summary": summary_payload,
            "results": result.get("results") or [],
        }
    )
    return response


@router.get("/watchlist/rules/{rule_id}/detail", response_model=WatchlistRuleDetailResponse)
def watchlist_rule_detail(
    rule_id: uuid.UUID,
    recent_limit: int = Query(default=5, ge=1, le=50),
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    _: PlanContext = Depends(require_plan_feature("search.alerts")),
    db: Session = Depends(get_db),
) -> WatchlistRuleDetailResponse:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    owner_filters = _owner_filters(user_id, org_id)
    try:
        payload = watchlist_service.collect_watchlist_rule_detail(
            db,
            rule_id=rule_id,
            owner_filters=owner_filters,
            recent_limit=recent_limit,
        )
    except ValueError as exc:
        detail = str(exc)
        if detail == "watchlist.rule_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "alerts.rule_not_found", "message": "워치리스트 룰을 찾을 수 없습니다."},
            )
        if detail == "watchlist.rule_not_watchlist":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "alerts.invalid_rule", "message": "워치리스트 룰이 아닙니다."},
            )
        raise
    return WatchlistRuleDetailResponse.model_validate(payload)


@router.get("/channels/schema", response_model=AlertChannelSchemaResponse)
def channel_schema(
    plan: PlanContext = Depends(require_plan_feature("search.alerts")),
) -> AlertChannelSchemaResponse:
    allowed = allowed_channels(plan.tier)
    definitions = list_channel_definitions(allowed)
    return AlertChannelSchemaResponse(channels=definitions)
