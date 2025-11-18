"""Admin LLM & Guardrail management endpoints wired to persistent stores."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import difflib
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from llm import guardrails, llm_service
from core.logging import get_logger
from schemas.api.admin import (
    AdminGuardrailBookmarkRequest,
    AdminGuardrailEvaluateRequest,
    AdminGuardrailEvaluateResponse,
    AdminGuardrailPolicyResponse,
    AdminGuardrailPolicySchema,
    AdminGuardrailPolicyUpdateRequest,
    AdminGuardrailSampleListResponse,
    AdminGuardrailSampleSchema,
    AdminLlmProfileListResponse,
    AdminLlmProfileResponse,
    AdminLlmProfileSchema,
    AdminLlmProfileUpsertRequest,
    AdminSystemPromptListResponse,
    AdminSystemPromptSchema,
    AdminSystemPromptUpdateRequest,
    PromptChannel,
)
from services import admin_llm_store
from services.admin_audit import append_audit_log
from web.deps_admin import require_admin_session, AdminSession
from web.routers.admin_utils import create_admin_router


def _build_guardrail_diff_lines(original: str, sanitized: str) -> List[Dict[str, str]]:
    diff = difflib.ndiff(original.splitlines(), sanitized.splitlines())
    result: List[Dict[str, str]] = []
    for entry in diff:
        prefix = entry[:2]
        text = entry[2:]
        if prefix == "  ":
            kind = "same"
        elif prefix == "+ ":
            kind = "added"
        elif prefix == "- ":
            kind = "removed"
        else:
            continue
        result.append({"kind": kind, "text": text})
        if len(result) >= 60:
            break
    return result

router = create_admin_router(
    prefix="/admin/llm",
    tags=["Admin LLM"],
)

_AUDIT_DIR = Path("uploads") / "admin"
logger = get_logger(__name__)

try:
    _startup_policy = admin_llm_store.load_guardrail_policy()
    guardrails.update_guardrail_blocklist(_startup_policy.get("blocklist", []))
    llm_service.set_guardrail_copy(
        (_startup_policy.get("userFacingCopy") or {}).get("fallback")
    )
except Exception:  # pragma: no cover - best-effort bootstrap
    pass


def _parse_prompt_channel_value(raw: str) -> PromptChannel:
    try:
        return PromptChannel(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "admin.invalid_prompt_channel", "message": f"Unknown prompt channel '{raw}'."},
        ) from exc


def _to_profile_schema(record: Dict[str, object]) -> AdminLlmProfileSchema:
    return AdminLlmProfileSchema(
        name=str(record.get("name") or ""),
        model=str(record.get("model") or ""),
        settings=dict(record.get("settings") or {}),
    )


@router.get(
    "/profiles",
    response_model=AdminLlmProfileListResponse,
    summary="LiteLLM 프로필 목록을 조회합니다.",
)
def list_llm_profiles() -> AdminLlmProfileListResponse:
    try:
        _, config = admin_llm_store.load_litellm_config()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "admin.llm_config_unavailable", "message": str(exc)},
        ) from exc

    profiles = [
        _to_profile_schema(profile) for profile in admin_llm_store.list_litellm_profiles(config)
    ]
    if not profiles:
        profiles.append(
            AdminLlmProfileSchema(
                name="default-chat",
                model="judge_model",
                settings={"temperature": 0.3, "top_p": 0.9},
            )
        )
    return AdminLlmProfileListResponse(profiles=profiles)


@router.put(
    "/profiles/{profile_name}",
    response_model=AdminLlmProfileResponse,
    summary="LiteLLM 프로필을 생성하거나 업데이트합니다.",
)
def upsert_llm_profile(profile_name: str, payload: AdminLlmProfileUpsertRequest) -> AdminLlmProfileResponse:
    try:
        config_path, config = admin_llm_store.load_litellm_config()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "admin.llm_config_unavailable", "message": str(exc)},
        ) from exc

    try:
        profile_dict = admin_llm_store.upsert_litellm_profile(
            config,
            name=profile_name,
            model=payload.model,
            settings=payload.settings,
        )
        admin_llm_store.save_litellm_config(config_path, config)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "admin.llm_profile_write_failed", "message": str(exc)},
        ) from exc

    updated_at = datetime.now(timezone.utc).isoformat()
    append_audit_log(
        filename="llm_audit.jsonl",
        actor=payload.actor,
        action="profile_upsert",
        payload={"profile": profile_name, "note": payload.note},
    )
    updated = AdminLlmProfileSchema(**profile_dict)
    return AdminLlmProfileResponse(
        profile=updated,
        updatedAt=updated_at,
        updatedBy=payload.actor,
    )


@router.get(
    "/prompts/system",
    response_model=AdminSystemPromptListResponse,
    summary="시스템 프롬프트 목록을 조회합니다.",
)
def list_system_prompts(channel: PromptChannel | None = Query(default=None)) -> AdminSystemPromptListResponse:
    prompts = admin_llm_store.load_system_prompts()
    items: List[AdminSystemPromptSchema] = []
    for key, record in prompts.items():
        parsed_channel = _parse_prompt_channel_value(key)
        schema = AdminSystemPromptSchema(
            channel=parsed_channel,
            prompt=str(record.get("prompt") or ""),
            updatedAt=record.get("updatedAt"),
            updatedBy=record.get("updatedBy"),
        )
        if channel is None or schema.channel == channel:
            items.append(schema)
    if channel and not items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="prompt_not_found")
    return AdminSystemPromptListResponse(items=items)


@router.put(
    "/prompts/system",
    response_model=AdminSystemPromptSchema,
    summary="시스템 프롬프트를 업데이트합니다.",
)
def update_system_prompt(payload: AdminSystemPromptUpdateRequest) -> AdminSystemPromptSchema:
    record = admin_llm_store.update_system_prompt(
        channel=payload.channel,
        prompt=payload.prompt,
        actor=payload.actor,
        note=payload.note,
    )
    return AdminSystemPromptSchema(
        channel=payload.channel,
        prompt=record.get("prompt", ""),
        updatedAt=record.get("updatedAt"),
        updatedBy=record.get("updatedBy"),
    )


def _policy_from_store(raw: Dict[str, object]) -> AdminGuardrailPolicyResponse:
    policy_data = {
        "intentRules": raw.get("intentRules") or [],
        "blocklist": raw.get("blocklist") or [],
        "userFacingCopy": raw.get("userFacingCopy") or {},
    }
    meta = {
        "updatedAt": raw.get("updatedAt"),
        "updatedBy": raw.get("updatedBy"),
    }
    return AdminGuardrailPolicyResponse(
        policy=AdminGuardrailPolicySchema(**policy_data),
        **meta,
    )


@router.get(
    "/guardrails/policies",
    response_model=AdminGuardrailPolicyResponse,
    summary="현재 Guardrail 정책을 조회합니다.",
)
def read_guardrail_policy() -> AdminGuardrailPolicyResponse:
    payload = admin_llm_store.load_guardrail_policy()
    return _policy_from_store(payload)


@router.put(
    "/guardrails/policies",
    response_model=AdminGuardrailPolicyResponse,
    summary="Guardrail 정책을 업데이트합니다.",
)
def update_guardrail_policy(payload: AdminGuardrailPolicyUpdateRequest) -> AdminGuardrailPolicyResponse:
    record = admin_llm_store.update_guardrail_policy(
        intent_rules=[dict(rule) for rule in payload.intentRules],
        blocklist=list(payload.blocklist),
        user_facing_copy=dict(payload.userFacingCopy),
        actor=payload.actor,
        note=payload.note,
    )
    guardrails.update_guardrail_blocklist(record.get("blocklist", []))
    llm_service.set_guardrail_copy(
        (record.get("userFacingCopy") or {}).get("fallback")
    )
    return _policy_from_store(record)


@router.post(
    "/guardrails/evaluate",
    response_model=AdminGuardrailEvaluateResponse,
    summary="샘플 텍스트에 대해 Guardrail 평가를 수행합니다.",
)
def evaluate_guardrail_sample(
    payload: AdminGuardrailEvaluateRequest,
    session: AdminSession = Depends(require_admin_session),
) -> AdminGuardrailEvaluateResponse:
    sample = payload.sample or ""
    sanitized_text, guard_violation = guardrails.apply_answer_guard(sample)
    matched_rules = guardrails.matched_blocklist_terms(sample)
    if guard_violation and "guardrail_violation:" in guard_violation:
        pattern = guard_violation.split(":", 1)[-1]
        if pattern and pattern not in matched_rules:
            matched_rules.append(pattern)

    judge_result: Dict[str, object]
    if matched_rules or guard_violation:
        reason_hint = None
        if matched_rules:
            reason_hint = f"blocklist:{matched_rules[0]}"
        judge_result = {
            "decision": "block",
            "rag_mode": "none",
            "reason": reason_hint,
            "model_used": None,
        }
    else:
        judge_result = llm_service.assess_query_risk(sample)

    result = "pass"
    if matched_rules or guard_violation:
        result = "blocked"
    else:
        decision = (judge_result or {}).get("decision")
        if decision in {"block"}:
            result = "blocked"
        elif decision in {"semi_pass"}:
            result = "warn"

    channels = payload.channels or ["default"]
    sanitized_output = sanitized_text if guard_violation else sample
    line_diff = _build_guardrail_diff_lines(sample, sanitized_output)

    details: Dict[str, object] = {
        "channels": channels,
        "matchedRules": matched_rules,
        "judge": judge_result,
        "sanitizedSample": sanitized_output,
        "safeMessage": guardrails.SAFE_MESSAGE,
    }
    logged_at = datetime.now(timezone.utc).isoformat()
    try:
        append_audit_log(
            filename="llm_audit.jsonl",
            actor=session.actor,
            action="guardrail_evaluate",
            payload={
                "channels": channels,
                "result": result,
                "matchedRules": matched_rules,
                "judgeDecision": (judge_result or {}).get("decision"),
                "samplePreview": sanitized_output[:200],
            },
        )
    except Exception:  # pragma: no cover - audit logging best-effort
        logger.debug("Failed to append guardrail evaluation audit entry.", exc_info=True)

    sample_record = admin_llm_store.record_guardrail_sample(
        actor=session.actor,
        sample=sample,
        sanitized_sample=sanitized_output,
        result=result,
        channels=channels,
        matched_rules=matched_rules,
        judge_decision=(judge_result or {}).get("decision"),
        audit_file="llm_audit.jsonl",
        line_diff=line_diff,
    )

    return AdminGuardrailEvaluateResponse(
        result=result,
        details=details,
        loggedAt=logged_at,
        auditFile="llm_audit.jsonl",
        sampleId=sample_record.get("sampleId"),
        lineDiff=line_diff,
    )



@router.get(
    "/guardrails/samples",
    response_model=AdminGuardrailSampleListResponse,
    summary="Guardrail 평가 샘플 히스토리를 조회합니다.",
)
def list_guardrail_samples(
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(default=None, alias="q"),
    bookmarked: Optional[bool] = Query(default=None),
) -> AdminGuardrailSampleListResponse:
    raw_samples: List[Dict[str, Any]] = admin_llm_store.list_guardrail_samples(
        limit=limit + 1, search=search, bookmarked=bookmarked
    )
    has_more = len(raw_samples) > limit
    if has_more:
        raw_samples = raw_samples[:limit]
    items: List[AdminGuardrailSampleSchema] = []
    for item in raw_samples:
        try:
            items.append(AdminGuardrailSampleSchema(**item))
        except Exception:  # pragma: no cover - ignore malformed records
            continue
    next_cursor = raw_samples[-1].get("evaluatedAt") if has_more and raw_samples else None
    return AdminGuardrailSampleListResponse(items=items, hasMore=has_more, nextCursor=next_cursor)


@router.patch(
    "/guardrails/samples/{sample_id}/bookmark",
    response_model=AdminGuardrailSampleSchema,
    summary="Guardrail 샘플 북마크 상태를 변경합니다.",
)
def update_guardrail_sample_bookmark(
    sample_id: str, payload: AdminGuardrailBookmarkRequest
) -> AdminGuardrailSampleSchema:
    updated = admin_llm_store.update_guardrail_bookmark(sample_id, bookmarked=payload.bookmarked)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="sample_not_found")
    return AdminGuardrailSampleSchema(**updated)



@router.get(
    "/audit/logs",
    summary="LLM 감사 로그를 다운로드합니다.",
    response_class=FileResponse,
)
def download_llm_audit_log() -> FileResponse:
    audit_path = (_AUDIT_DIR / "llm_audit.jsonl").resolve()
    if not audit_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audit_log_not_found")
    return FileResponse(audit_path, media_type="application/json", filename="llm_audit.jsonl")
