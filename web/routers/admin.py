"""Admin quick action, session, and audit endpoints."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.env import env_bool, env_str
from database import get_db
from schemas.api.admin import (
    AdminCredentialLoginRequest,
    AdminSessionCreateRequest,
    AdminSessionResponse,
    AdminSessionRevokeResponse,
    PlanQuickAdjustRequest,
    TossWebhookReplayRequest,
    TossWebhookReplayResponse,
    WebhookAuditListResponse,
)
from schemas.api.plan import (
    PlanContextResponse,
    PlanFeatureFlagsSchema,
    PlanMemoryFlagsSchema,
    PlanQuotaSchema,
)
from services.admin_session_service import (
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    issue_admin_session,
    record_admin_audit_event,
    revoke_admin_session,
)
from services.auth_service import AuthServiceError, RequestContext, login_user
from services.google_id_token import (
    GoogleIdTokenVerificationError,
    verify_admin_google_id_token,
)
from services.payments.toss_webhook_audit import read_recent_webhook_entries
from services.payments.toss_webhook_replay import replay_toss_webhook_event
from services.plan_service import PlanContext, update_plan_context
from web.deps_admin import AdminSession, load_admin_token_map, require_admin_session

router = APIRouter(prefix="/admin", tags=["Admin"])
protected_router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin_session)])

_AUDIT_DIR = Path("uploads") / "admin"
_ALLOWED_EMAILS = {
    email.strip().lower()
    for email in (env_str("ADMIN_ALLOWED_EMAILS") or "").split(",")
    if email and email.strip()
}
_MFA_SECRET_MAP: Dict[str, str] = {}
for entry in (env_str("ADMIN_MFA_SECRETS") or "").split(","):
    entry = entry.strip()
    if not entry or ":" not in entry:
        continue
    email, secret = entry.split(":", 1)
    email = email.strip().lower()
    secret = secret.strip().replace(" ", "")
    if email and secret:
        _MFA_SECRET_MAP[email] = secret.upper()
_REQUIRE_MFA = env_bool("ADMIN_REQUIRE_MFA", False)


def _client_ip(request: Request) -> Optional[str]:
    client = request.client
    return client.host if client else None


def _ensure_allowed_email(email: str) -> None:
    if _ALLOWED_EMAILS and email.lower() not in _ALLOWED_EMAILS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "admin.unauthorized_user", "message": "운영자 목록에 포함되지 않은 계정입니다."},
        )


def _verify_mfa(email: str, otp: Optional[str]) -> None:
    secret = _MFA_SECRET_MAP.get(email.lower())
    if secret:
        if not otp:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "admin.mfa_required", "message": "MFA 코드가 필요합니다."},
            )
        totp = pyotp.TOTP(secret)
        if not totp.verify(otp, valid_window=1):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "admin.mfa_invalid", "message": "잘못된 MFA 코드입니다."},
            )
    elif _REQUIRE_MFA:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "admin.mfa_not_configured", "message": "이 계정에는 MFA가 구성되지 않았습니다."},
        )


def _resolve_actor_from_token(token: str, actor_override: Optional[str]) -> str:
    token_map = load_admin_token_map()
    if not token_map:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "admin.tokens_unconfigured", "message": "ADMIN_API_TOKENS 환경 값이 설정되지 않았습니다."},
        )
    actor = token_map.get(token.strip())
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "admin.invalid_token", "message": "유효하지 않은 토큰입니다."},
        )
    if actor_override:
        override = actor_override.strip()
        if override:
            actor = override
    return actor


def _set_session_cookie(response: Response, token: str, max_age_seconds: int) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite=SESSION_COOKIE_SAMESITE,
        max_age=max_age_seconds,
        path="/",
    )


def _delete_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


@router.post(
    "/session",
    response_model=AdminSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="운영 토큰을 검증하고 세션을 발급합니다.",
)
def create_admin_session(
    payload: AdminSessionCreateRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AdminSessionResponse:
    auth_metadata: Dict[str, Any]
    if payload.idToken:
        try:
            google_info = verify_admin_google_id_token(payload.idToken)
        except GoogleIdTokenVerificationError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc
        actor = google_info.email
        auth_metadata = {
            "auth": "google_sso",
            "subject": google_info.subject,
            "hosted_domain": google_info.hosted_domain,
        }
    else:
        actor = _resolve_actor_from_token(payload.token or "", payload.actorOverride)
        auth_metadata = {"auth": "static_token"}

    issue = issue_admin_session(
        db,
        actor=actor,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        metadata=auth_metadata,
    )
    ttl = max(0, int((issue.record.expires_at - issue.record.issued_at).total_seconds()))
    _set_session_cookie(response, issue.token, ttl)
    record_admin_audit_event(
        db,
        actor=issue.record.actor,
        event_type="login",
        session_id=issue.record.id,
        route=request.url.path,
        method=request.method,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        metadata=auth_metadata,
    )
    return AdminSessionResponse(
        actor=issue.record.actor,
        issuedAt=issue.record.issued_at.isoformat(),
        tokenHint=issue.record.token_hint,
        sessionId=issue.record.id,
        expiresAt=issue.record.expires_at.isoformat(),
    )


@router.post(
    "/auth/login",
    response_model=AdminSessionResponse,
    summary="이메일+비밀번호(+MFA)로 운영자 세션을 생성합니다.",
)
def create_admin_session_with_credentials(
    payload: AdminCredentialLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AdminSessionResponse:
    email = payload.email.strip().lower()
    _ensure_allowed_email(email)
    _verify_mfa(email, payload.otp)

    context = RequestContext(ip=_client_ip(request), user_agent=request.headers.get("user-agent"))
    try:
        login_user(
            db,
            {"email": payload.email, "password": payload.password, "rememberMe": False},
            context=context,
        )
    except AuthServiceError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    role_row = db.execute(
        text('SELECT role FROM "users" WHERE LOWER(email) = :email'),
        {"email": email},
    ).mappings().first()
    if not role_row or role_row.get("role") not in {"admin", "owner"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "admin.role_unauthorized", "message": "운영자 권한이 없는 계정입니다."},
        )

    issue = issue_admin_session(
        db,
        actor=email,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        metadata={"auth": "internal_credentials"},
    )
    ttl = max(0, int((issue.record.expires_at - issue.record.issued_at).total_seconds()))
    _set_session_cookie(response, issue.token, ttl)
    record_admin_audit_event(
        db,
        actor=email,
        event_type="login",
        session_id=issue.record.id,
        route=request.url.path,
        method=request.method,
        ip=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        metadata={"auth": "internal_credentials"},
    )
    return AdminSessionResponse(
        actor=issue.record.actor,
        issuedAt=issue.record.issued_at.isoformat(),
        tokenHint=issue.record.token_hint,
        sessionId=issue.record.id,
        expiresAt=issue.record.expires_at.isoformat(),
    )


@router.delete(
    "/session",
    response_model=AdminSessionRevokeResponse,
    summary="로그아웃(세션 삭제).",
)
def revoke_admin_session_endpoint(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AdminSessionRevokeResponse:
    cookie_token = request.cookies.get(SESSION_COOKIE_NAME)
    session: Optional[AdminSession] = getattr(request.state, "admin_session", None)
    revoked = False
    if cookie_token:
        revoked = revoke_admin_session(db, token=cookie_token)
    elif session and session.session_id:
        revoked = revoke_admin_session(db, session_id=session.session_id)
    _delete_session_cookie(response)
    if session:
        record_admin_audit_event(
            db,
            actor=session.actor,
            event_type="logout",
            session_id=session.session_id,
            route=request.url.path,
            method=request.method,
            ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    return AdminSessionRevokeResponse(revoked=revoked)


@protected_router.get(
    "/session",
    response_model=AdminSessionResponse,
    summary="관리자 세션 상태를 확인합니다.",
)
def read_admin_session(request: Request) -> AdminSessionResponse:
    session: Optional[AdminSession] = getattr(request.state, "admin_session", None)
    if session is None:
        session = require_admin_session(request)
    return AdminSessionResponse(
        actor=session.actor,
        issuedAt=session.issued_at.isoformat(),
        tokenHint=session.token_hint,
        sessionId=session.session_id,
        expiresAt=session.expires_at.isoformat() if session.expires_at else None,
    )


@protected_router.get(
    "/webhooks/toss/events",
    response_model=WebhookAuditListResponse,
    summary="Toss 웹훅 감사 로그 목록.",
)
def list_toss_webhook_audit_entries(limit: int = Query(100, ge=1, le=500)) -> WebhookAuditListResponse:
    items = list(read_recent_webhook_entries(limit=limit))
    return WebhookAuditListResponse(items=items)


@protected_router.post(
    "/webhooks/toss/replay",
    response_model=TossWebhookReplayResponse,
    summary="지정한 Toss 웹훅을 다시 실행합니다.",
)
def replay_toss_webhook(payload: TossWebhookReplayRequest) -> TossWebhookReplayResponse:
    try:
        result = replay_toss_webhook_event(payload.transmissionId)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "admin.webhook_replay_invalid", "message": str(exc)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "admin.webhook_replay_failed", "message": str(exc)},
        ) from exc

    return TossWebhookReplayResponse(**result)


@protected_router.post(
    "/plan/quick-adjust",
    response_model=PlanContextResponse,
    summary="플랜 퀵 조정을 실행합니다.",
)
def apply_plan_quick_adjust(payload: PlanQuickAdjustRequest) -> PlanContextResponse:
    quota_overrides: Dict[str, Any] = {}
    if payload.quota is not None:
        quota_overrides = payload.quota.model_dump(exclude_none=True)

    try:
        context = update_plan_context(
            plan_tier=payload.planTier,
            entitlements=payload.entitlements,
            quota=quota_overrides,
            expires_at=payload.expiresAt,
            updated_by=payload.actor,
            change_note=payload.changeNote,
            trigger_checkout=payload.triggerCheckout,
            force_checkout_requested=payload.forceCheckoutRequested,
            memory_flags=payload.memoryFlags.model_dump() if payload.memoryFlags else None,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "admin.plan_invalid", "message": str(exc)},
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "admin.plan_update_failed", "message": str(exc)},
        ) from exc

    return _plan_context_to_response(context)


@protected_router.get(
    "/plan/audit/logs",
    summary="플랜 변경 감사 로그를 다운로드합니다.",
    response_class=FileResponse,
)
def download_plan_audit_log() -> FileResponse:
    audit_path = (_AUDIT_DIR / "plan_audit.jsonl").resolve()
    if not audit_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="audit_log_not_found")
    return FileResponse(audit_path, media_type="application/json", filename="plan_audit.jsonl")


def _plan_context_to_response(context: PlanContext) -> PlanContextResponse:
    feature_flags = context.feature_flags()
    return PlanContextResponse(
        planTier=context.tier,
        entitlements=sorted(context.entitlements),
        expiresAt=context.expires_at.isoformat() if context.expires_at else None,
        checkoutRequested=context.checkout_requested,
        updatedAt=context.updated_at.isoformat() if context.updated_at else None,
        updatedBy=context.updated_by,
        changeNote=context.change_note,
        quota=PlanQuotaSchema(**context.quota.to_dict()),
        featureFlags=PlanFeatureFlagsSchema(
            searchCompare=feature_flags.get("search.compare", False),
            searchAlerts=feature_flags.get("search.alerts", False),
            searchExport=feature_flags.get("search.export", False),
            ragCore=feature_flags.get("rag.core", False),
            evidenceInlinePdf=feature_flags.get("evidence.inline_pdf", False),
            evidenceDiff=feature_flags.get("evidence.diff", False),
            timelineFull=feature_flags.get("timeline.full", False),
        ),
        memoryFlags=PlanMemoryFlagsSchema(
            watchlist=context.memory_watchlist_enabled,
            digest=context.memory_digest_enabled,
            chat=context.memory_chat_enabled,
        ),
    )


router.include_router(protected_router)
