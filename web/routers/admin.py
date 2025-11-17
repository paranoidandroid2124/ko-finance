"""Admin quick action, session, and audit endpoints."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.env import env_bool, env_str
from database import get_db
from schemas.api.admin import (
    AdminScimTokenCreateRequest,
    AdminScimTokenCreateResponse,
    AdminScimTokenListResponse,
    AdminScimTokenSchema,
    AdminCredentialLoginRequest,
    AdminSsoCredentialResponse,
    AdminSsoCredentialUpsertRequest,
    AdminSsoProviderCreateRequest,
    AdminSsoProviderListResponse,
    AdminSsoProviderResponse,
    AdminSsoProviderSchema,
    AdminSsoProviderUpdateRequest,
    AdminSessionCreateRequest,
    AdminSessionResponse,
    AdminSessionRevokeResponse,
    PlanQuickAdjustRequest,
    TossWebhookReplayRequest,
    TossWebhookReplayResponse,
    WebhookAuditListResponse,
)
from schemas.api.plan import PlanContextResponse
from services.admin_session_service import (
    SESSION_COOKIE_NAME,
    SESSION_COOKIE_SAMESITE,
    SESSION_COOKIE_SECURE,
    issue_admin_session,
    record_admin_audit_event,
    revoke_admin_session,
)
from services.admin_shared import parse_iso_datetime
from services.auth_service import AuthServiceError, RequestContext, login_user
from services.google_id_token import (
    GoogleIdTokenVerificationError,
    verify_admin_google_id_token,
)
from services.payments.toss_webhook_audit import read_recent_webhook_entries
from services.payments.toss_webhook_replay import replay_toss_webhook_event
from services.plan_service import PlanContext, update_plan_context
from services.plan_serializers import serialize_plan_context
from services import sso_provider_service
from services.sso_provider_cache import invalidate_provider_cache
from web.deps_admin import AdminSession, load_admin_token_map, require_admin_session

router = APIRouter(prefix="/admin", tags=["Admin"])
protected_router = APIRouter(tags=["Admin"], dependencies=[Depends(require_admin_session)])

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


def _parse_uuid_value(value: Optional[str], *, field_name: str) -> Optional[UUID]:
    if not value:
        return None
    try:
        return UUID(str(value).strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "admin.invalid_uuid", "message": f"{field_name} 값이 올바른 UUID 형식이 아닙니다."},
        ) from exc


def _isoformat(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


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


def _serialize_provider(
    provider,
    *,
    credentials: Optional[Dict[str, Optional[str]]] = None,
) -> AdminSsoProviderSchema:
    scopes = list(provider.scopes or [])
    attribute_mapping = dict(provider.attribute_mapping or {})
    metadata = dict(provider.metadata or {})
    return AdminSsoProviderSchema(
        id=str(provider.id),
        slug=provider.slug,
        providerType=provider.provider_type,
        displayName=provider.display_name,
        orgId=str(provider.org_id) if provider.org_id else None,
        issuer=provider.issuer,
        audience=provider.audience,
        spEntityId=provider.sp_entity_id,
        acsUrl=provider.acs_url,
        metadataUrl=provider.metadata_url,
        idpSsoUrl=provider.idp_sso_url,
        authorizationUrl=provider.authorization_url,
        tokenUrl=provider.token_url,
        userinfoUrl=provider.userinfo_url,
        redirectUri=provider.redirect_uri,
        scopes=scopes,
        attributeMapping=attribute_mapping,
        defaultPlanTier=provider.default_plan_tier,
        defaultRole=provider.default_role,
        defaultOrgSlug=provider.default_org_slug,
        autoProvisionOrgs=provider.auto_provision_orgs,
        enabled=provider.enabled,
        metadata=metadata,
        createdAt=_isoformat(provider.created_at),
        updatedAt=_isoformat(provider.updated_at),
        credentials=dict(credentials or {}),
    )


def _serialize_scim_token(record) -> AdminScimTokenSchema:
    return AdminScimTokenSchema(
        id=str(record.id),
        tokenPrefix=record.token_prefix,
        description=record.description,
        createdBy=record.created_by,
        createdAt=_isoformat(record.created_at) or "",
        lastUsedAt=_isoformat(record.last_used_at),
        expiresAt=_isoformat(record.expires_at),
        revokedAt=_isoformat(record.revoked_at),
    )


def _get_provider_or_404(db: Session, provider_id: UUID):
    provider = sso_provider_service.get_sso_provider(db, provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "admin.sso_provider_not_found", "message": "요청한 SSO 프로바이더를 찾을 수 없습니다."},
        )
    return provider


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


@protected_router.get(
    "/sso/providers",
    response_model=AdminSsoProviderListResponse,
    summary="구성된 SSO 프로바이더 목록을 조회합니다.",
)
def list_sso_providers_endpoint(
    providerType: Optional[str] = Query(default=None, description="필터링할 타입(SAML/OIDC)."),
    db: Session = Depends(get_db),
) -> AdminSsoProviderListResponse:
    records = sso_provider_service.list_sso_providers(db, provider_type=providerType)
    items: List[AdminSsoProviderSchema] = []
    for record in records:
        creds = sso_provider_service.get_masked_credentials(db, record.id)
        items.append(_serialize_provider(record, credentials=creds))
    return AdminSsoProviderListResponse(items=items)


@protected_router.post(
    "/sso/providers",
    response_model=AdminSsoProviderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="SSO 프로바이더를 생성합니다.",
)
def create_sso_provider_endpoint(
    payload: AdminSsoProviderCreateRequest,
    admin_session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db),
) -> AdminSsoProviderResponse:
    org_id = _parse_uuid_value(payload.orgId, field_name="orgId")
    try:
        record = sso_provider_service.create_sso_provider(
            db,
            slug=payload.slug,
            provider_type=payload.providerType,
            display_name=payload.displayName,
            org_id=org_id,
            issuer=payload.issuer,
            audience=payload.audience,
            sp_entity_id=payload.spEntityId,
            acs_url=payload.acsUrl,
            metadata_url=payload.metadataUrl,
            idp_sso_url=payload.idpSsoUrl,
            authorization_url=payload.authorizationUrl,
            token_url=payload.tokenUrl,
            userinfo_url=payload.userinfoUrl,
            redirect_uri=payload.redirectUri,
            scopes=payload.scopes,
            attribute_mapping=payload.attributeMapping,
            default_plan_tier=payload.defaultPlanTier,
            default_role=payload.defaultRole,
            default_org_slug=payload.defaultOrgSlug,
            auto_provision_orgs=payload.autoProvisionOrgs,
            metadata=payload.metadata,
        )
        db.commit()
        db.refresh(record)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "admin.sso_provider_invalid", "message": str(exc)},
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "admin.sso_provider_error", "message": "SSO 프로바이더 생성에 실패했습니다."},
        ) from exc

    record_admin_audit_event(
        db,
        actor=admin_session.actor,
        event_type="sso.provider.create",
        session_id=admin_session.session_id,
        route="/admin/sso/providers",
        method="POST",
        ip=None,
        user_agent=None,
        metadata={"providerId": str(record.id), "slug": record.slug, "providerType": record.provider_type},
    )
    invalidate_provider_cache(slug=record.slug, provider_type=record.provider_type)
    creds = sso_provider_service.get_masked_credentials(db, record.id)
    return AdminSsoProviderResponse(provider=_serialize_provider(record, credentials=creds))


@protected_router.patch(
    "/sso/providers/{provider_id}",
    response_model=AdminSsoProviderResponse,
    summary="SSO 프로바이더 설정을 수정합니다.",
)
def update_sso_provider_endpoint(
    provider_id: UUID,
    payload: AdminSsoProviderUpdateRequest,
    admin_session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db),
) -> AdminSsoProviderResponse:
    provider = _get_provider_or_404(db, provider_id)
    try:
        record = sso_provider_service.update_sso_provider(
            db,
            provider_id=provider.id,
            display_name=payload.displayName,
            issuer=payload.issuer,
            audience=payload.audience,
            sp_entity_id=payload.spEntityId,
            acs_url=payload.acsUrl,
            metadata_url=payload.metadataUrl,
            idp_sso_url=payload.idpSsoUrl,
            authorization_url=payload.authorizationUrl,
            token_url=payload.tokenUrl,
            userinfo_url=payload.userinfoUrl,
            redirect_uri=payload.redirectUri,
            scopes=payload.scopes,
            attribute_mapping=payload.attributeMapping,
            default_plan_tier=payload.defaultPlanTier,
            default_role=payload.defaultRole,
            default_org_slug=payload.defaultOrgSlug,
            auto_provision_orgs=payload.autoProvisionOrgs,
            metadata=payload.metadata,
            enabled=payload.enabled,
        )
        db.commit()
        db.refresh(record)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "admin.sso_provider_invalid", "message": str(exc)},
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "admin.sso_provider_error", "message": "SSO 프로바이더 업데이트에 실패했습니다."},
        ) from exc

    record_admin_audit_event(
        db,
        actor=admin_session.actor,
        event_type="sso.provider.update",
        session_id=admin_session.session_id,
        route=f"/admin/sso/providers/{provider_id}",
        method="PATCH",
        ip=None,
        user_agent=None,
        metadata={"providerId": str(provider.id), "slug": provider.slug},
    )
    invalidate_provider_cache(slug=provider.slug, provider_type=provider.provider_type)
    creds = sso_provider_service.get_masked_credentials(db, provider.id)
    return AdminSsoProviderResponse(provider=_serialize_provider(record, credentials=creds))


@protected_router.post(
    "/sso/providers/{provider_id}/credentials",
    response_model=AdminSsoCredentialResponse,
    summary="SSO 자격증명을 저장/회전합니다.",
)
def upsert_sso_credential_endpoint(
    provider_id: UUID,
    payload: AdminSsoCredentialUpsertRequest,
    admin_session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db),
) -> AdminSsoCredentialResponse:
    provider = _get_provider_or_404(db, provider_id)
    try:
        credential = sso_provider_service.store_provider_credential(
            db,
            provider_id=provider.id,
            credential_type=payload.credentialType,
            secret_value=payload.secretValue,
            created_by=admin_session.actor,
        )
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "admin.sso_credential_error", "message": "자격증명 저장에 실패했습니다."},
        ) from exc

    record_admin_audit_event(
        db,
        actor=admin_session.actor,
        event_type="sso.provider.credential",
        session_id=admin_session.session_id,
        route=f"/admin/sso/providers/{provider_id}/credentials",
        method="POST",
        ip=None,
        user_agent=None,
        metadata={"providerId": str(provider.id), "credentialType": payload.credentialType},
    )
    invalidate_provider_cache(slug=provider.slug, provider_type=provider.provider_type)
    return AdminSsoCredentialResponse(
        credentialType=payload.credentialType,
        maskedSecret=credential.secret_masked,
        version=credential.version,
    )


@protected_router.get(
    "/sso/providers/{provider_id}/scim-tokens",
    response_model=AdminScimTokenListResponse,
    summary="SCIM 토큰 목록을 조회합니다.",
)
def list_scim_tokens_endpoint(
    provider_id: UUID,
    db: Session = Depends(get_db),
) -> AdminScimTokenListResponse:
    provider = _get_provider_or_404(db, provider_id)
    records = sso_provider_service.list_scim_tokens(db, provider.id)
    items = [_serialize_scim_token(record) for record in records]
    return AdminScimTokenListResponse(items=items)


@protected_router.post(
    "/sso/providers/{provider_id}/scim-tokens",
    response_model=AdminScimTokenCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="새로운 SCIM 토큰을 발급합니다.",
)
def create_scim_token_endpoint(
    provider_id: UUID,
    payload: AdminScimTokenCreateRequest,
    admin_session: AdminSession = Depends(require_admin_session),
    db: Session = Depends(get_db),
) -> AdminScimTokenCreateResponse:
    provider = _get_provider_or_404(db, provider_id)
    expires_at = parse_iso_datetime(payload.expiresAt)
    if payload.expiresAt and expires_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "admin.invalid_datetime", "message": "expiresAt 값을 파싱할 수 없습니다."},
        )
    token = sso_provider_service.generate_scim_token(
        db,
        provider.id,
        created_by=admin_session.actor,
        description=payload.description,
        expires_at=expires_at,
    )
    db.commit()
    record_admin_audit_event(
        db,
        actor=admin_session.actor,
        event_type="sso.scim.token.create",
        session_id=admin_session.session_id,
        route=f"/admin/sso/providers/{provider_id}/scim-tokens",
        method="POST",
        ip=None,
        user_agent=None,
        metadata={"providerId": str(provider.id)},
    )
    return AdminScimTokenCreateResponse(token=token)


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

    return serialize_plan_context(context)


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


router.include_router(protected_router)
