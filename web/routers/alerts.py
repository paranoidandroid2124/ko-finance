from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.api.alerts import (
    AlertChannelSchemaResponse,
    AlertRuleCreateRequest,
    AlertRuleListResponse,
    AlertRuleResponse,
    AlertRuleUpdateRequest,
    AlertPlanInfo,
)
from services.alert_service import (
    PlanQuotaError,
    allowed_channels,
    create_alert_rule,
    get_alert_rule,
    list_alert_rules,
    serialize_alert,
    serialize_plan_capabilities,
    update_alert_rule,
    archive_alert_rule,
)
from services.alert_channel_registry import list_channel_definitions
from services.plan_service import PlanContext
from web.deps import get_plan_context

router = APIRouter(prefix="/alerts", tags=["Alerts"])


def _parse_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="잘못된 UUID 형식입니다.")


def _owner_filters(user_id: Optional[uuid.UUID], org_id: Optional[uuid.UUID]) -> dict:
    return {"user_id": user_id, "org_id": org_id}


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
    plan: PlanContext = Depends(get_plan_context),
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
    plan: PlanContext = Depends(get_plan_context),
) -> AlertRuleResponse:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    filters = _owner_filters(user_id, org_id)
    try:
        rule = create_alert_rule(
            db,
            plan_tier=plan.tier,
            owner_filters=filters,
            name=payload.name,
            description=payload.description,
            condition=payload.condition.dict(),
            channels=[channel.model_dump() for channel in payload.channels],
            message_template=payload.messageTemplate,
            evaluation_interval_minutes=payload.evaluationIntervalMinutes,
            window_minutes=payload.windowMinutes,
            cooldown_minutes=payload.cooldownMinutes,
            max_triggers_per_day=payload.maxTriggersPerDay,
            extras=payload.extras,
        )
        db.commit()
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
    plan: PlanContext = Depends(get_plan_context),
) -> AlertRuleResponse:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    filters = _owner_filters(user_id, org_id)
    rule = get_alert_rule(db, rule_id=alert_id, owner_filters=filters)
    if rule is None:
        raise _plan_http_exception(status.HTTP_404_NOT_FOUND, "alerts.not_found", "알림을 찾을 수 없습니다.")
    changes = payload.model_dump(exclude_unset=True)
    if payload.condition is not None:
        changes["condition"] = payload.condition.dict()
    if payload.channels is not None:
        changes["channels"] = [channel.model_dump() for channel in payload.channels]
    try:
        updated = update_alert_rule(db, rule=rule, plan_tier=plan.tier, changes=changes)
        db.commit()
    except PlanQuotaError as exc:
        db.rollback()
        raise _plan_http_exception(status.HTTP_403_FORBIDDEN, exc.code, str(exc))
    except ValueError as exc:
        db.rollback()
        raise _plan_http_exception(status.HTTP_400_BAD_REQUEST, "alerts.invalid_payload", str(exc))
    db.refresh(updated)
    return _response_from_rule(updated)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    alert_id: uuid.UUID,
    x_user_id: Optional[str] = Header(default=None),
    x_org_id: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
    plan: PlanContext = Depends(get_plan_context),
) -> None:
    user_id = _parse_uuid(x_user_id)
    org_id = _parse_uuid(x_org_id)
    filters = _owner_filters(user_id, org_id)
    rule = get_alert_rule(db, rule_id=alert_id, owner_filters=filters)
    if rule is None:
        return
    if plan.tier == "free":
        raise _plan_http_exception(
            status.HTTP_403_FORBIDDEN,
            "plan.locked_action",
            "현재 플랜에서는 알림 삭제가 허용되지 않습니다.",
        )
    archive_alert_rule(db, rule=rule)
    db.commit()
@router.get("/channels/schema", response_model=AlertChannelSchemaResponse)
def channel_schema(
    plan: PlanContext = Depends(get_plan_context),
) -> AlertChannelSchemaResponse:
    allowed = allowed_channels(plan.tier)
    definitions = list_channel_definitions(allowed)
    return AlertChannelSchemaResponse(channels=definitions)
