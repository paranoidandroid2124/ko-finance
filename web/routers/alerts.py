from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Mapping, Sequence, Dict, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from core.env import env_int
from core.logging import get_logger
from database import get_db
from schemas.api.alerts import (
    AlertChannelSchema,
    AlertChannelSchemaResponse,
    AlertEventMatchResponse,
    AlertRuleCreateRequest,
    AlertRuleListResponse,
    AlertRuleResponse,
    AlertRuleSimulationRequest,
    AlertRuleSimulationResponse,
    AlertRuleUpdateRequest,
    AlertRuleStatsResponse,
    AlertPlanInfo,
    AlertRulePreset,
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
    preview_alert_rule,
    rule_delivery_stats,
    serialize_alert,
    serialize_plan_capabilities,
    update_alert_rule,
    archive_alert_rule,
)
from services.alerts import list_alert_presets, record_preset_usage
from services.alert_channel_registry import list_channel_definitions
from services import alert_rate_limiter, watchlist_service
from services.audit_log import audit_alert_event
from services.user_settings_service import UserLightMemSettings
from services.alerts_watchlist_support import (
    resolve_lightmem_user_id,
    load_user_lightmem_settings,
    watchlist_memory_enabled,
    owner_filters as build_owner_filters,
)
from services.plan_service import PlanContext
from services.web_utils import parse_uuid
from web.deps import require_plan_feature
from web.quota_guard import enforce_quota

router = APIRouter(prefix="/alerts", tags=["Alerts"])
logger = get_logger(__name__)

ALERTS_WRITE_RATE_LIMIT = env_int("ALERTS_WRITE_RATE_LIMIT", 30, minimum=1)
ALERTS_WRITE_RATE_WINDOW_SECONDS = env_int("ALERTS_WRITE_RATE_WINDOW_SECONDS", 900, minimum=60)


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


def _extract_preset_metadata(extras: Optional[Mapping[str, object]]) -> Optional[Dict[str, str]]:
    if not extras:
        return None
    preset_id = extras.get("presetId") or extras.get("preset_id")
    if not preset_id:
        return None
    bundle = extras.get("presetBundle") or extras.get("preset_bundle")
    return {
        "presetId": str(preset_id),
        "bundle": str(bundle) if bundle else None,
    }


def _track_preset_usage(
    preset_meta: Mapping[str, Optional[str]],
    *,
    plan: PlanContext,
    user_id: Optional[uuid.UUID],
    org_id: Optional[uuid.UUID],
    channels: Optional[Sequence[AlertChannelSchema]],
    rule_id: Optional[uuid.UUID] = None,
) -> None:
    channel_types = []
    if channels:
        for channel in channels:
            channel_types.append(channel.type)
    try:
        record_preset_usage(
            preset_id=str(preset_meta.get("presetId")),
            bundle=preset_meta.get("bundle"),
            plan_tier=plan.tier,
            channel_types=channel_types,
            user_id=user_id,
            org_id=org_id,
            rule_id=rule_id,
        )
    except Exception:  # pragma: no cover - analytics logging best effort
        logger.debug("Failed to record preset usage", exc_info=True)


@router.get("/watchlist/rules/{rule_id}/detail", response_model=WatchlistRuleDetailResponse)
def watchlist_rule_detail(
    rule_id: uuid.UUID,
    recent_limit: int = Query(default=5, ge=1, le=50),
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    _: PlanContext = Depends(require_plan_feature("search.alerts")),
    db: Session = Depends(get_db),
) -> WatchlistRuleDetailResponse:
    user_id = parse_uuid(x_user_id)
    org_id = parse_uuid(x_org_id)
    filters = build_owner_filters(user_id, org_id)
    try:
        payload = watchlist_service.collect_watchlist_rule_detail(
            db,
            rule_id=rule_id,
            owner_filters=filters,
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
