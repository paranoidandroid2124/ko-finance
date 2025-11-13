"""이메일·비밀번호 인증 엔드포인트."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from schemas.api.auth import (
    AccountUnlockConfirmRequest,
    AccountUnlockConfirmResponse,
    AccountUnlockRequest,
    AccountUnlockResponse,
    EmailVerifyRequest,
    EmailVerifyResendRequest,
    EmailVerifyResendResponse,
    EmailVerifyResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    PasswordResetConfirmRequest,
    PasswordResetConfirmResponse,
    PasswordResetRequest,
    PasswordResetResponse,
    RegisterRequest,
    RegisterResponse,
    SessionRefreshRequest,
    SessionRefreshResponse,
    OidcAuthorizeResponse,
)
from services.auth_service import (
    AuthServiceError,
    RequestContext,
    build_oidc_authorize_url,
    complete_oidc_login,
    confirm_account_unlock,
    confirm_password_reset,
    consume_saml_assertion,
    generate_saml_metadata,
    login_user,
    logout_session,
    request_account_unlock,
    refresh_session,
    register_user,
    request_password_reset,
    resend_verification_email,
    verify_email,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


def _ctx(request: Request) -> RequestContext:
    client_host = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return RequestContext(ip=client_host, user_agent=user_agent)


def _raise(exc: AuthServiceError) -> None:
    detail = {"code": exc.code, "message": str(exc)}
    if getattr(exc, "extra", None):
        detail.update(exc.extra)
    raise HTTPException(
        status_code=exc.status_code,
        detail=detail,
        headers=exc.headers,
    ) from exc


@router.get(
    "/saml/metadata",
    summary="SAML SP metadata 다운로드",
)
def saml_metadata_route() -> Response:
    try:
        metadata = generate_saml_metadata()
    except AuthServiceError as exc:
        _raise(exc)
    return Response(content=metadata, media_type="application/samlmetadata+xml")


@router.post(
    "/saml/acs",
    response_model=LoginResponse,
    summary="SAML Assertion Consumer Service",
)
async def saml_acs_route(
    request: Request,
    saml_response: str = Form(..., alias="SAMLResponse"),
    relay_state: Optional[str] = Form(default=None, alias="RelayState"),
    db: Session = Depends(get_db),
) -> LoginResponse:
    try:
        result = consume_saml_assertion(
            db,
            saml_response=saml_response,
            relay_state=relay_state,
            context=_ctx(request),
        )
    except AuthServiceError as exc:
        _raise(exc)
    return LoginResponse(
        accessToken=result.access_token,
        refreshToken=result.refresh_token,
        expiresIn=result.expires_in,
        sessionId=result.session_id,
        sessionToken=result.session_token,
        user=result.user,
    )


@router.get(
    "/oidc/authorize",
    response_model=OidcAuthorizeResponse,
    summary="OIDC 로그인 URL 생성",
)
def oidc_authorize_route(
    request: Request,
    returnTo: Optional[str] = None,
    orgSlug: Optional[str] = None,
    prompt: Optional[str] = None,
    loginHint: Optional[str] = None,
) -> OidcAuthorizeResponse:
    try:
        result = build_oidc_authorize_url(
            return_to=returnTo,
            org_slug=orgSlug,
            prompt=prompt,
            login_hint=loginHint,
            context=_ctx(request),
        )
    except AuthServiceError as exc:
        _raise(exc)
    return OidcAuthorizeResponse(
        authorizationUrl=result.authorization_url,
        state=result.state,
        expiresIn=result.expires_in,
    )


@router.get(
    "/oidc/callback",
    response_model=LoginResponse,
    summary="OIDC 코드 교환",
)
def oidc_callback_route(
    code: str,
    state: str,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    try:
        result = complete_oidc_login(
            db,
            code=code,
            state=state,
            context=_ctx(request),
        )
    except AuthServiceError as exc:
        _raise(exc)
    return LoginResponse(
        accessToken=result.access_token,
        refreshToken=result.refresh_token,
        expiresIn=result.expires_in,
        sessionId=result.session_id,
        sessionToken=result.session_token,
        user=result.user,
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="이메일·비밀번호 가입",
)
def register_route(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> RegisterResponse:
    try:
        result = register_user(db, payload.model_dump(), context=_ctx(request))
    except AuthServiceError as exc:
        _raise(exc)
    return RegisterResponse(
        userId=result.user_id,
        requiresVerification=True,
        verificationExpiresIn=result.verification_expires_in,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="이메일·비밀번호 로그인",
)
def login_route(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    try:
        result = login_user(db, payload.model_dump(), context=_ctx(request))
    except AuthServiceError as exc:
        _raise(exc)
    return LoginResponse(
        accessToken=result.access_token,
        refreshToken=result.refresh_token,
        expiresIn=result.expires_in,
        sessionId=result.session_id,
        sessionToken=result.session_token,
        user=result.user,
    )


@router.post(
    "/email/verify",
    response_model=EmailVerifyResponse,
    summary="이메일 검증 토큰 확인",
)
def email_verify_route(
    payload: EmailVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> EmailVerifyResponse:
    try:
        result = verify_email(db, token=payload.token, context=_ctx(request))
    except AuthServiceError as exc:
        _raise(exc)
    return EmailVerifyResponse(emailVerified=result.email_verified, redirectUrl=None)


@router.post(
    "/email/verify/resend",
    response_model=EmailVerifyResendResponse,
    summary="이메일 검증 메일 재발송",
)
def email_verify_resend_route(
    payload: EmailVerifyResendRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> EmailVerifyResendResponse:
    try:
        result = resend_verification_email(db, email=payload.email, context=_ctx(request))
    except AuthServiceError as exc:
        _raise(exc)
    return EmailVerifyResendResponse(sent=result.sent)


@router.post(
    "/password-reset/request",
    response_model=PasswordResetResponse,
    summary="비밀번호 재설정 메일 발송",
)
def password_reset_request_route(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> PasswordResetResponse:
    try:
        result = request_password_reset(db, email=payload.email, context=_ctx(request))
    except AuthServiceError as exc:
        _raise(exc)
    return PasswordResetResponse(sent=result.sent, cooldownSeconds=result.cooldown_seconds)


@router.post(
    "/password-reset/confirm",
    response_model=PasswordResetConfirmResponse,
    summary="비밀번호 재설정 완료",
)
def password_reset_confirm_route(
    payload: PasswordResetConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> PasswordResetConfirmResponse:
    try:
        result = confirm_password_reset(
            db,
            token=payload.token,
            new_password=payload.newPassword,
            context=_ctx(request),
        )
    except AuthServiceError as exc:
        _raise(exc)
    return PasswordResetConfirmResponse(success=result.success)


@router.post(
    "/account/unlock/request",
    response_model=AccountUnlockResponse,
    summary="계정 잠금 해제 메일 발송",
)
def account_unlock_request_route(
    payload: AccountUnlockRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AccountUnlockResponse:
    try:
        result = request_account_unlock(db, email=payload.email, context=_ctx(request))
    except AuthServiceError as exc:
        _raise(exc)
    return AccountUnlockResponse(sent=result.sent)


@router.post(
    "/account/unlock/confirm",
    response_model=AccountUnlockConfirmResponse,
    summary="계정 잠금 해제 확인",
)
def account_unlock_confirm_route(
    payload: AccountUnlockConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AccountUnlockConfirmResponse:
    try:
        result = confirm_account_unlock(db, token=payload.token, context=_ctx(request))
    except AuthServiceError as exc:
        _raise(exc)
    return AccountUnlockConfirmResponse(unlocked=result.unlocked)


@router.post(
    "/session/refresh",
    response_model=SessionRefreshResponse,
    summary="Access Token 재발급",
)
def session_refresh_route(
    payload: SessionRefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> SessionRefreshResponse:
    try:
        result = refresh_session(
            db,
            refresh_token=payload.refreshToken,
            session_id=payload.sessionId,
            session_token=payload.sessionToken,
            context=_ctx(request),
        )
    except AuthServiceError as exc:
        _raise(exc)
    return SessionRefreshResponse(
        accessToken=result.access_token,
        refreshToken=result.refresh_token,
        expiresIn=result.expires_in,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="세션 종료",
)
def logout_route(
    payload: LogoutRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    try:
        logout_session(
            db,
            session_id=payload.sessionId,
            all_devices=payload.allDevices,
            refresh_token=payload.refreshToken,
            context=_ctx(request),
        )
    except AuthServiceError as exc:
        _raise(exc)
