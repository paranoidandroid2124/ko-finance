"""이메일·비밀번호 인증 서비스 로직."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import ipaddress
import json
import logging
import re
import secrets
import textwrap
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple, cast
from urllib.parse import urlencode

import httpx
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from lxml import etree
from signxml import InvalidSignature, XMLVerifier
from sqlalchemy import text
from sqlalchemy.orm import Session
from xmltodict import parse as parse_xml

from core.auth.constants import ALLOWED_SIGNUP_CHANNELS, DEFAULT_SIGNUP_CHANNEL, SignupChannel
from core.plan_constants import PlanTier, SUPPORTED_PLAN_TIERS
from core.env import env_bool, env_int, env_str
from database import IS_POSTGRES
from services import onboarding_service
from services.workspace_bootstrap import bootstrap_workspace_for_org
from services.auth_tokens import (
    AuthTokenError,
    AuthTokenType,
    MagicToken,
    consume_magic_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    issue_magic_token,
)

from services.audit_log import audit_rbac_event
from services.entitlement_service import entitlement_service
from services.rbac_service import ROLE_ORDER

try:  # pragma: no cover - optional rate limiter
    from services.auth_rate_limiter import RateLimitResult, check_limit as _check_limit
except Exception:  # pragma: no cover - fallback when redis is unavailable

    @dataclass(frozen=True)
    class RateLimitResult:  # type: ignore[redefinition]
        allowed: bool = True
        remaining: Optional[int] = None
        reset_at: Optional[datetime] = None
        backend_error: bool = True

    def _check_limit(*args, **kwargs):  # type: ignore[no-redef]
        return RateLimitResult()

logger = logging.getLogger(__name__)


def _noop_send_email(*args, **kwargs) -> None:
    logger.debug("Email delivery disabled; skipping send.")


send_verification_email = _noop_send_email
send_password_reset_email = _noop_send_email
send_account_unlock_email = _noop_send_email
send_account_locked_email = _noop_send_email

_ARGON_TIME_COST = env_int("AUTH_ARGON2_TIME_COST", 4, minimum=1)
_ARGON_MEMORY_COST = env_int("AUTH_ARGON2_MEMORY_COST", 131072, minimum=8192)
_ARGON_PARALLELISM = env_int("AUTH_ARGON2_PARALLELISM", 1, minimum=1)
_EMAIL_VERIFY_TTL = env_int("AUTH_EMAIL_VERIFY_TTL_SECONDS", 30 * 60, minimum=60)
_PASSWORD_RESET_TTL = env_int("AUTH_PASSWORD_RESET_TTL_SECONDS", 30 * 60, minimum=60)
_LOGIN_FAILURE_LIMIT = env_int("AUTH_LOGIN_FAILURE_LIMIT", 5, minimum=3)
_ACCOUNT_LOCK_SECONDS = env_int("AUTH_ACCOUNT_LOCK_SECONDS", 15 * 60, minimum=60)
_ACCOUNT_UNLOCK_TTL = env_int("AUTH_ACCOUNT_UNLOCK_TTL_SECONDS", 15 * 60, minimum=60)
_REMEMBER_REFRESH_TTL = env_int("AUTH_REMEMBER_REFRESH_TTL_SECONDS", 60 * 60 * 24 * 30, minimum=600)
_LOGIN_IP_RATE_LIMIT = env_int("AUTH_LOGIN_IP_RATE_LIMIT", 10, minimum=3)
_LOGIN_IP_RATE_WINDOW_SECONDS = env_int("AUTH_LOGIN_IP_RATE_WINDOW_SECONDS", 300, minimum=60)
_LOGIN_EMAIL_RATE_LIMIT = env_int("AUTH_LOGIN_EMAIL_RATE_LIMIT", 5, minimum=3)
_LOGIN_EMAIL_RATE_WINDOW_SECONDS = env_int("AUTH_LOGIN_EMAIL_RATE_WINDOW_SECONDS", 300, minimum=60)
_PASSWORD_MIN_LENGTH = env_int("AUTH_PASSWORD_MIN_LENGTH", 12, minimum=8)
_PASSWORD_REQUIRE_UPPER = env_bool("AUTH_PASSWORD_REQUIRE_UPPER", True)
_PASSWORD_REQUIRE_LOWER = env_bool("AUTH_PASSWORD_REQUIRE_LOWER", True)
_PASSWORD_REQUIRE_DIGIT = env_bool("AUTH_PASSWORD_REQUIRE_DIGIT", True)
_PASSWORD_REQUIRE_SYMBOL = env_bool("AUTH_PASSWORD_REQUIRE_SYMBOL", True)

_PASSWORD_HASHER = PasswordHasher(
    time_cost=_ARGON_TIME_COST,
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        *,
        extra: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.extra = dict(extra or {})
        self.headers = dict(headers or {}) if headers else None


class RegisterUserUseCase:
    """Encapsulates the user registration flow for improved testability."""

    def __init__(self, session: Session, payload: Dict[str, Any], context: RequestContext):
        self.session = session
        self.payload = payload
        self.context = context
        self.now = datetime.now(timezone.utc)
        self.raw_email = (payload.get("email") or "").strip()
        self.email = _normalize_email(self.raw_email)
        self.signup_channel = _normalize_signup_channel(payload.get("signupChannel"))
        self.name = (payload.get("name") or "").strip() or None

    def execute(self) -> RegisterResult:
        self._validate_payload()
        self._enforce_limits()
        user_id, org_uuid, verification_token = self._persist_user()
        if org_uuid is not None:
            _ensure_org_subscription(org_uuid, "free", source="auth.register")
        send_verification_email(email=self.raw_email or self.email, token=verification_token, name=self.name)
        return RegisterResult(user_id=user_id, verification_expires_in=_EMAIL_VERIFY_TTL)

    def _validate_payload(self) -> None:
        if not self.payload.get("acceptTerms"):
            raise AuthServiceError("auth.invalid_payload", "약관 동의가 필요합니다.", 400)
        if not self.payload.get("password"):
            raise AuthServiceError("auth.invalid_payload", "비밀번호가 필요합니다.", 400)

    def _enforce_limits(self) -> None:
        _enforce_rate_limit("auth.register.ip", self.context.ip, limit=5, window_seconds=600)
        _enforce_rate_limit("auth.register.email", self.email, limit=3, window_seconds=3600)

    def _persist_user(self) -> Tuple[str, Optional[uuid.UUID], str]:
        hashed = _hash_password(self.payload["password"])
        verification_token_value: Optional[str] = None
        org_uuid: Optional[uuid.UUID] = None
        with self.session.begin():
            existing = self.session.execute(
                text(
                    f"""
                    SELECT id, password_hash
                    FROM "users"
                    WHERE LOWER(email) = :email
                    {_FOR_UPDATE}
                    """
                ),
                {"email": self.email},
            ).mappings().first()

            if existing:
                if existing["password_hash"]:
                    raise AuthServiceError("auth.email_taken", "이미 가입된 이메일입니다.", 409)
                user_id = str(existing["id"])
                self.session.execute(
                    text(
                        """
                        UPDATE "users"
                        SET password_hash = :password_hash,
                            signup_channel = :signup_channel,
                            password_updated_at = :now
                        WHERE id = :id
                        """
                    ),
                    {
                        "password_hash": hashed,
                        "signup_channel": self.signup_channel,
                        "id": user_id,
                        "now": self.now,
                    },
                )
            else:
                row = self.session.execute(
                    text(
                        """
                        INSERT INTO "users" (
                            email, name, password_hash, signup_channel, failed_attempts, locked_until, plan_tier, role
                        )
                        VALUES (:email_original, :name, :password_hash, :signup_channel, 0, NULL, 'free', 'user')
                        RETURNING id
                        """
                    ),
                    {
                        "email_original": self.payload["email"].strip(),
                        "name": self.name,
                        "password_hash": hashed,
                        "signup_channel": self.signup_channel,
                    },
                ).mappings().first()
                user_id = str(row["id"])

            user_uuid = uuid.UUID(user_id)
            org_uuid = _ensure_default_org(self.session, user_uuid)
            token = _issue_token_with_audit(
                self.session,
                user_id=user_id,
                token_type="email_verify",
                identifier=self.email,
                ttl_seconds=_EMAIL_VERIFY_TTL,
                context=self.context,
                audit_event="register",
                audit_channel=self.signup_channel,
            )
            verification_token_value = token.token
        return user_id, org_uuid, verification_token_value or ""


class LoginUserUseCase:
    """Handles login orchestration and side effects."""

    def __init__(self, session: Session, payload: Dict[str, Any], context: RequestContext):
        self.session = session
        self.payload = payload
        self.context = context
        self.now = datetime.now(timezone.utc)
        self.email = _normalize_email(payload.get("email", ""))
        self.remember_me = bool(payload.get("rememberMe"))
        self.plan_slug: Optional[str] = None
        self.org_uuid: Optional[uuid.UUID] = None

    def execute(self) -> LoginResult:
        self._enforce_limits()
        with self.session.begin():
            user = self._load_user()
            self._verify_credentials(user)
            _revoke_expired_sessions(self.session, str(user["id"]))
            user_uuid = uuid.UUID(str(user["id"]))
            _mark_login_success(self.session, str(user["id"]), self.context, self.now)
            self.org_uuid = _ensure_default_org(self.session, user_uuid)
            needs_onboarding = onboarding_service.ensure_first_login_metadata(
                self.session,
                user_id=str(user["id"]),
            )
            result = self._issue_result(user, needs_onboarding)
        if self.org_uuid is not None:
            _ensure_org_subscription(self.org_uuid, self.plan_slug, source="auth.login")
        return result

    def _enforce_limits(self) -> None:
        _enforce_rate_limit("auth.login.ip", self.context.ip, limit=_LOGIN_IP_RATE_LIMIT, window_seconds=_LOGIN_IP_RATE_WINDOW_SECONDS)
        _enforce_rate_limit("auth.login.email", self.email, limit=_LOGIN_EMAIL_RATE_LIMIT, window_seconds=_LOGIN_EMAIL_RATE_WINDOW_SECONDS)

    def _load_user(self) -> Mapping[str, Any]:
        user = self.session.execute(
            text(
                f"""
                SELECT
                    id, email, password_hash, plan_tier, role,
                    email_verified_at, failed_attempts, locked_until
                FROM "users"
                WHERE LOWER(email) = :email
                {_FOR_UPDATE}
                """
            ),
            {"email": self.email},
        ).mappings().first()
        if not user or not user["password_hash"]:
            _handle_failed_attempt(self.session, user, self.context, self.now)
            raise AuthServiceError("auth.invalid_credentials", "이메일 또는 비밀번호가 올바르지 않습니다.", 401)
        return user

    def _verify_credentials(self, user: Mapping[str, Any]) -> None:
        if user["locked_until"] and user["locked_until"] > self.now:
            raise AuthServiceError("auth.account_locked", "계정이 잠겨있습니다. 잠시 후 다시 시도해주세요.", 423)
        try:
            _PASSWORD_HASHER.verify(user["password_hash"], self.payload.get("password") or "")
        except VerifyMismatchError:
            _handle_failed_attempt(self.session, user, self.context, self.now)
            raise AuthServiceError("auth.invalid_credentials", "이메일 또는 비밀번호가 올바르지 않습니다.", 401)
        if not user["email_verified_at"]:
            raise AuthServiceError("auth.needs_verification", "이메일 인증이 필요합니다.", 403)

    def _issue_result(self, user: Mapping[str, Any], needs_onboarding: bool) -> LoginResult:
        self.plan_slug = user["plan_tier"]
        return _issue_login_result(
            self.session,
            user_id=str(user["id"]),
            email=user["email"],
            plan=user["plan_tier"],
            role=user["role"],
            email_verified=True,
            channel="email",
            context=self.context,
            now=self.now,
            remember_me=self.remember_me,
            onboarding_required=needs_onboarding,
            org_id=str(self.org_uuid) if self.org_uuid else None,
        )


def register_user(session: Session, payload: Dict[str, Any], *, context: RequestContext) -> RegisterResult:
    return RegisterUserUseCase(session, payload, context).execute()


def login_user(session: Session, payload: Dict[str, Any], *, context: RequestContext) -> LoginResult:
    return LoginUserUseCase(session, payload, context).execute()


def verify_email(
    session: Session,
    *,
    token: str,
    context: RequestContext,
) -> EmailVerifyResult:
    with session.begin():
        try:
            magic = consume_magic_token(session, token=token, token_type="email_verify")
        except AuthTokenError as exc:
            raise AuthServiceError(exc.code, str(exc), 400 if exc.code != "auth.token_expired" else 410) from exc

        session.execute(
            text(
                """
                UPDATE "users"
                SET email_verified_at = COALESCE(email_verified_at, NOW())
                WHERE id = :id
                """
            ),
            {"id": magic.user_id},
        )
        _record_audit_event(
            session,
            event_type="email_verify",
            user_id=magic.user_id,
            channel="email",
            context=context,
            metadata={"token_id": magic.id},
        )
    return EmailVerifyResult(email_verified=True)


def resend_verification_email(
    session: Session,
    *,
    email: str,
    context: RequestContext,
) -> VerificationResendResult:
    normalized = _normalize_email(email)
    _enforce_rate_limit("auth.verify_resend.ip", context.ip, limit=5, window_seconds=600)
    _enforce_rate_limit("auth.verify_resend.email", normalized, limit=3, window_seconds=3600)
    token_value: Optional[str] = None
    recipient_email: Optional[str] = None
    recipient_name: Optional[str] = None

    with session.begin():
        user = session.execute(
            text(
                f"""
                SELECT id, email, name, email_verified_at
                FROM "users"
                WHERE LOWER(email) = :email
                {_FOR_UPDATE}
                """
            ),
            {"email": normalized},
        ).mappings().first()
        if not user:
            raise AuthServiceError("auth.user_not_found", "존재하지 않는 이메일입니다.", 404)
        if user.get("email_verified_at"):
            raise AuthServiceError("auth.already_verified", "이미 인증이 완료된 이메일입니다.", 409)
        token = _issue_token_with_audit(
            session,
            user_id=str(user["id"]),
            token_type="email_verify",
            identifier=normalized,
            ttl_seconds=_EMAIL_VERIFY_TTL,
            context=context,
            audit_event="email_verify",
            audit_metadata={"action": "resend"},
        )
        token_value = token.token
        recipient_email = user["email"]
        recipient_name = user.get("name")
    if token_value and recipient_email:
        send_verification_email(email=recipient_email, token=token_value, name=recipient_name)
    return VerificationResendResult(sent=True)


def request_password_reset(
    session: Session,
    *,
    email: str,
    context: RequestContext,
) -> PasswordResetRequestResult:
    normalized = _normalize_email(email)
    _enforce_rate_limit("auth.password_reset.email", normalized, limit=5, window_seconds=1800)
    reset_token_value: Optional[str] = None
    recipient_email: Optional[str] = None
    recipient_name: Optional[str] = None

    with session.begin():
        user = session.execute(
            text(
                """
                SELECT id, email, name, email_verified_at
                FROM "users"
                WHERE LOWER(email) = :email
                """
            ),
            {"email": normalized},
        ).mappings().first()

        if not user:
            raise AuthServiceError("auth.user_not_found", "존재하지 않는 이메일입니다.", 404)
        if not user["email_verified_at"]:
            raise AuthServiceError("auth.needs_verification", "이메일 인증 후 비밀번호를 재설정할 수 있습니다.", 409)

        recipient_email = user["email"]
        recipient_name = user.get("name")
        token = _issue_token_with_audit(
            session,
            user_id=str(user["id"]),
            token_type="password_reset",
            identifier=normalized,
            ttl_seconds=_PASSWORD_RESET_TTL,
            context=context,
            audit_event="password_reset_request",
        )
        reset_token_value = token.token
    if reset_token_value and recipient_email:
        send_password_reset_email(email=recipient_email, token=reset_token_value, name=recipient_name)
    return PasswordResetRequestResult(sent=True, cooldown_seconds=None)


def confirm_password_reset(
    session: Session,
    *,
    token: str,
    new_password: str,
    context: RequestContext,
) -> PasswordResetConfirmResult:
    hashed = _hash_password(new_password)
    with session.begin():
        try:
            magic = consume_magic_token(session, token=token, token_type="password_reset")
        except AuthTokenError as exc:
            raise AuthServiceError(exc.code, str(exc), 400 if exc.code != "auth.token_expired" else 410) from exc

        now = datetime.now(timezone.utc)
        session.execute(
            text(
                """
                UPDATE "users"
                SET password_hash = :password_hash,
                    password_updated_at = :now,
                    failed_attempts = 0,
                    locked_until = NULL
                WHERE id = :id
                """
            ),
            {"password_hash": hashed, "now": now, "id": magic.user_id},
        )
        session.execute(
            text(
                """
                UPDATE session_tokens
                SET revoked_at = NOW()
                WHERE user_id = :user_id
                  AND revoked_at IS NULL
                """
            ),
            {"user_id": magic.user_id},
        )
        _record_audit_event(
            session,
            event_type="password_reset",
            user_id=magic.user_id,
            channel="email",
            context=context,
            metadata={"token_id": magic.id},
        )
    return PasswordResetConfirmResult(success=True)


def refresh_session(
    session: Session,
    *,
    refresh_token: str,
    session_id: str,
    session_token: str,
    context: RequestContext,
) -> SessionRefreshResult:
    try:
        payload = decode_token(refresh_token, scope="refresh")
    except AuthTokenError as exc:
        raise AuthServiceError(exc.code, str(exc), 401 if exc.code == "auth.token_expired" else 400) from exc
    if payload.get("session_id") != session_id:
        raise AuthServiceError("auth.token_invalid", "세션 정보가 일치하지 않습니다.", 409)

    with session.begin():
        row = session.execute(
            text(
                f"""
                SELECT id, user_id, session_token, refresh_jti, revoked_at, expires_at, metadata
                FROM session_tokens
                WHERE id = :id
                  AND refresh_jti = :refresh_jti
                {_FOR_UPDATE}
                """
            ),
            {"id": session_id, "refresh_jti": payload["jti"]},
        ).mappings().first()
        if not row:
            raise AuthServiceError("auth.session_invalid", "세션 정보를 찾을 수 없습니다.", 409)
        if row["revoked_at"] or row["expires_at"] < datetime.now(timezone.utc):
            raise AuthServiceError("auth.session_expired", "세션이 만료되었습니다.", 409)
        if row["session_token"] != session_token:
            raise AuthServiceError("auth.token_invalid", "세션 토큰이 일치하지 않습니다.", 409)

        user = session.execute(
            text(
                """
                SELECT id, email, plan_tier, role, email_verified_at
                FROM "users"
                WHERE id = :id
                """
            ),
            {"id": row["user_id"]},
        ).mappings().first()
        if not user:
            raise AuthServiceError("auth.user_not_found", "사용자를 찾을 수 없습니다.", 404)

        _revoke_expired_sessions(session, str(user["id"]))
        access_token, access_ttl = create_access_token(
            user_id=str(user["id"]),
            email=user["email"],
            plan=user["plan_tier"],
            role=user["role"],
            email_verified=bool(user["email_verified_at"]),
            session_id=session_id,
        )
        session_metadata = row.get("metadata") if isinstance(row, Mapping) else None
        remember_me = False
        if isinstance(session_metadata, Mapping):
            remember_me = bool(session_metadata.get("remember_me"))
        refresh_jti = str(uuid.uuid4())
        new_refresh_token, refresh_ttl = create_refresh_token(
            user_id=str(user["id"]),
            session_id=session_id,
            refresh_jti=refresh_jti,
            ttl_seconds=_REMEMBER_REFRESH_TTL if remember_me else None,
        )
        session.execute(
            text(
                """
                UPDATE session_tokens
                SET refresh_jti = :refresh_jti,
                    last_used_at = NOW(),
                    expires_at = :expires_at
                WHERE id = :id
                """
            ),
            {
                "refresh_jti": refresh_jti,
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=refresh_ttl),
                "id": session_id,
            },
        )
    return SessionRefreshResult(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=access_ttl,
    )


def request_account_unlock(
    session: Session,
    *,
    email: str,
    context: RequestContext,
) -> AccountUnlockRequestResult:
    normalized = _normalize_email(email)
    _enforce_rate_limit("auth.unlock.ip", context.ip, limit=5, window_seconds=600)
    _enforce_rate_limit("auth.unlock.email", normalized, limit=3, window_seconds=1800)
    token_value: Optional[str] = None
    recipient_email: Optional[str] = None
    recipient_name: Optional[str] = None

    with session.begin():
        user = session.execute(
            text(
                f"""
                SELECT id, email, name, locked_until
                FROM "users"
                WHERE LOWER(email) = :email
                {_FOR_UPDATE}
                """
            ),
            {"email": normalized},
        ).mappings().first()
        if not user:
            raise AuthServiceError("auth.user_not_found", "존재하지 않는 이메일입니다.", 404)
        now = datetime.now(timezone.utc)
        locked_until = user.get("locked_until")
        if not locked_until or locked_until <= now:
            raise AuthServiceError("auth.unlock_not_required", "계정이 잠겨있지 않습니다.", 409)
        token = _issue_token_with_audit(
            session,
            user_id=str(user["id"]),
            token_type="account_unlock",
            identifier=normalized,
            ttl_seconds=_ACCOUNT_UNLOCK_TTL,
            context=context,
            audit_event="lock",
            audit_metadata={"action": "unlock_requested"},
        )
        token_value = token.token
        recipient_email = user["email"]
        recipient_name = user.get("name")
    if token_value and recipient_email:
        send_account_unlock_email(email=recipient_email, token=token_value, name=recipient_name)
    return AccountUnlockRequestResult(sent=True)


def confirm_account_unlock(
    session: Session,
    *,
    token: str,
    context: RequestContext,
) -> AccountUnlockConfirmResult:
    with session.begin():
        try:
            magic = consume_magic_token(session, token=token, token_type="account_unlock")
        except AuthTokenError as exc:
            raise AuthServiceError(exc.code, str(exc), 400 if exc.code != "auth.token_expired" else 410) from exc

        session.execute(
            text(
                """
                UPDATE "users"
                SET failed_attempts = 0,
                    locked_until = NULL
                WHERE id = :id
                """
            ),
            {"id": magic.user_id},
        )
        _record_audit_event(
            session,
            event_type="unlock",
            user_id=magic.user_id,
            channel="email",
            context=context,
            metadata={"token_id": magic.id},
        )
    return AccountUnlockConfirmResult(unlocked=True)


def logout_session(
    session: Session,
    *,
    session_id: str,
    all_devices: bool,
    refresh_token: Optional[str],
    context: RequestContext,
) -> None:
    with session.begin():
        if all_devices:
            user_id = None
            if refresh_token:
                try:
                    payload = decode_token(refresh_token, scope="refresh")
                    user_id = payload["sub"]
                except AuthTokenError:
                    user_id = None
            if not user_id:
                row = session.execute(
                    text("SELECT user_id FROM session_tokens WHERE id = :id"),
                    {"id": session_id},
                ).mappings().first()
                user_id = str(row["user_id"]) if row else None
            if not user_id:
                return
            session.execute(
                text(
                    """
                    UPDATE session_tokens
                    SET revoked_at = NOW()
                    WHERE user_id = :user_id
                      AND revoked_at IS NULL
                    """
                ),
                {"user_id": user_id},
            )
            _record_audit_event(
                session,
                event_type="logout",
                user_id=user_id,
                channel="email",
                context=context,
                metadata={"all_devices": True},
            )
        else:
            session.execute(
                text(
                    """
                    UPDATE session_tokens
                    SET revoked_at = NOW()
                    WHERE id = :id
                      AND revoked_at IS NULL
                    """
                ),
                {"id": session_id},
            )
            _record_audit_event(
                session,
                event_type="logout",
                user_id=None,
                channel="email",
                context=context,
                metadata={"session_id": session_id},
            )


def generate_saml_metadata(config_override: Optional[SamlProviderConfig] = None) -> str:
    """Return SP metadata XML for IdP configuration."""
    config = config_override or _SAML_CONFIG
    if not (config.enabled and config.sp_entity_id and config.acs_url):
        raise AuthServiceError("auth.saml_disabled", "SAML 서비스가 비활성화되어 있습니다.", 404)
    cert_block = ""
    cert_body = _sanitize_certificate(config.sp_certificate)
    if cert_body:
        cert_block = (
            "<KeyDescriptor use=\"signing\">"
            "<ds:KeyInfo xmlns:ds=\"http://www.w3.org/2000/09/xmldsig#\">"
            "<ds:X509Data><ds:X509Certificate>"
            f"{cert_body}"
            "</ds:X509Certificate></ds:X509Data>"
            "</ds:KeyInfo>"
            "</KeyDescriptor>"
        )
    metadata = f"""<?xml version="1.0" encoding="UTF-8"?>
<EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata" entityID="{config.sp_entity_id}">
  <SPSSODescriptor AuthnRequestsSigned="false" WantAssertionsSigned="true" protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    {cert_block}
    <AssertionConsumerService index="1" isDefault="true" Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" Location="{config.acs_url}"/>
  </SPSSODescriptor>
</EntityDescriptor>"""
    return metadata.strip()


def consume_saml_assertion(
    session: Session,
    *,
    saml_response: str,
    relay_state: Optional[str],
    context: RequestContext,
    config_override: Optional[SamlProviderConfig] = None,
) -> LoginResult:
    """Handle SAMLResponse POSTs from the IdP."""
    config = config_override or _SAML_CONFIG
    if not config.enabled or not config.acs_url or not config.sp_entity_id:
        raise AuthServiceError("auth.saml_disabled", "SAML 서비스가 비활성화되어 있습니다.", 404)
    try:
        xml_payload = base64.b64decode(saml_response, validate=True)
    except binascii.Error as exc:
        raise AuthServiceError("auth.saml_invalid_payload", "SAMLResponse 디코딩에 실패했습니다.", 400) from exc
    _validate_saml_signature(xml_payload, config)
    try:
        document = parse_xml(xml_payload)
    except Exception as exc:  # pragma: no cover - XML parsing guard
        raise AuthServiceError("auth.saml_invalid_payload", "SAML 응답을 파싱할 수 없습니다.", 400) from exc
    response = document.get("samlp:Response") or document.get("Response")
    if not response:
        raise AuthServiceError("auth.saml_invalid_response", "SAML Response 노드를 찾을 수 없습니다.", 400)
    destination = response.get("@Destination") or response.get("Destination")
    if destination and destination.rstrip("/") != config.acs_url.rstrip("/"):
        raise AuthServiceError("auth.saml_destination_mismatch", "Destination 값이 일치하지 않습니다.", 400)
    _validate_saml_issue_instant(response)
    response_issuer = _coerce_text(_extract_first(response, ["saml:Issuer", "Issuer"]))
    _validate_saml_issuer(response_issuer, config, source="Response")
    assertion = _extract_first(response, ["saml:Assertion", "Assertion"])
    if not assertion:
        raise AuthServiceError("auth.saml_missing_assertion", "Assertion 정보가 없습니다.", 400)
    assertion_issuer = _coerce_text(_extract_first(assertion, ["saml:Issuer", "Issuer"]))
    _validate_saml_issuer(assertion_issuer, config, source="Assertion")
    conditions = _extract_first(assertion, ["saml:Conditions", "Conditions"])
    audience_restriction = _extract_first(conditions, ["saml:AudienceRestriction", "AudienceRestriction"]) if conditions else None
    audience_value = _coerce_text(_extract_first(audience_restriction, ["saml:Audience", "Audience"])) if audience_restriction else None
    if audience_value and audience_value != config.sp_entity_id:
        raise AuthServiceError("auth.saml_audience_mismatch", "Audience 값이 일치하지 않습니다.", 403)
    _enforce_saml_temporal_conditions(conditions)
    attribute_statement = _extract_first(assertion, ["saml:AttributeStatement", "AttributeStatement"])
    attributes = _extract_attribute_map(attribute_statement)
    if relay_state:
        attributes["RelayState"] = relay_state
    name_id = _extract_name_id(assertion)
    email = attributes.get(config.email_attribute) or name_id
    if not email:
        raise AuthServiceError("auth.saml_missing_email", "SAML Assertion에 이메일이 없습니다.", 400)
    raw_role = (attributes.get(config.role_attribute) or "").strip().lower()
    mapped_role = config.role_mapping.get(raw_role, raw_role)
    rbac_role = _normalize_rbac_role_value(mapped_role, default=config.default_role)
    user_role = "admin" if raw_role in {"admin", "owner"} else "user"
    identity = SsoIdentity(
        provider="saml",
        email=email,
        display_name=attributes.get(config.name_attribute) or attributes.get("displayName") or name_id,
        external_id=attributes.get("externalId") or name_id,
        plan_tier=attributes.get("planTier") or config.default_plan_tier,
        user_role=user_role,
        org_id=attributes.get("orgId"),
        org_slug=attributes.get(config.org_attribute) or config.default_org_slug,
        org_name=attributes.get("orgName") or attributes.get("company"),
        rbac_role=rbac_role,
        attributes=attributes,
    )
    return _complete_sso_login(
        session,
        identity=identity,
        default_plan=config.default_plan_tier,
        default_org_slug=config.default_org_slug,
        auto_provision_org=config.auto_provision_orgs,
        default_rbac_role=config.default_role,
        context=context,
    )


def build_oidc_authorize_url(
    *,
    return_to: Optional[str],
    org_slug: Optional[str],
    prompt: Optional[str],
    login_hint: Optional[str],
    context: RequestContext,
    provider_slug: Optional[str] = None,
    config_override: Optional[OidcProviderConfig] = None,
) -> OidcAuthorizeResult:
    """Construct the OIDC authorization URL + state payload."""
    config = config_override or _OIDC_CONFIG
    if not (
        config.enabled
        and config.authorization_url
        and config.client_id
        and config.redirect_uri
    ):
        raise AuthServiceError("auth.oidc_disabled", "OIDC 서비스가 비활성화되어 있습니다.", 404)
    nonce = secrets.token_urlsafe(16)
    payload: Dict[str, Any] = {
        "provider": "oidc",
        "nonce": nonce,
        "exp": int((datetime.now(timezone.utc) + timedelta(seconds=_SSO_STATE_TTL_SECONDS)).timestamp()),
    }
    if return_to:
        payload["returnTo"] = return_to
    if org_slug:
        payload["orgSlug"] = org_slug
    if provider_slug:
        payload["providerSlug"] = provider_slug
    state = _encode_state(payload)
    params: Dict[str, Any] = {
        "client_id": config.client_id,
        "response_type": "code",
        "redirect_uri": config.redirect_uri,
        "scope": " ".join(config.scopes),
        "state": state,
        "nonce": nonce,
    }
    if prompt:
        params["prompt"] = prompt
    if login_hint:
        params["login_hint"] = login_hint
    url = f"{config.authorization_url}?{urlencode(params)}"
    return OidcAuthorizeResult(authorization_url=url, state=state, expires_in=_SSO_STATE_TTL_SECONDS)


def complete_oidc_login(
    session: Session,
    *,
    code: str,
    state: str,
    context: RequestContext,
    config_override: Optional[OidcProviderConfig] = None,
) -> LoginResult:
    """Exchange an OIDC authorization code for tokens + login."""
    config = config_override or _OIDC_CONFIG
    if not (
        config.enabled
        and config.token_url
        and config.userinfo_url
        and config.client_id
        and config.client_secret
        and config.redirect_uri
    ):
        raise AuthServiceError("auth.oidc_disabled", "OIDC 서비스가 비활성화되어 있습니다.", 404)
    payload = _decode_state(state)
    if payload.get("provider") != "oidc":
        raise AuthServiceError("auth.oidc_invalid_state", "상태 토큰이 일치하지 않습니다.", 400)
    token_request = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.redirect_uri,
        "client_id": config.client_id,
        "client_secret": config.client_secret,
    }
    try:
        with httpx.Client(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
            token_resp = client.post(config.token_url, data=token_request, headers={"Accept": "application/json"})
            token_resp.raise_for_status()
            token_data = token_resp.json()
            userinfo_resp = client.get(
                config.userinfo_url,
                headers={"Authorization": f"Bearer {token_data.get('access_token')}"},
                timeout=httpx.Timeout(10.0, connect=5.0),
            )
            userinfo_resp.raise_for_status()
            userinfo = userinfo_resp.json()
    except httpx.HTTPError as exc:
        raise AuthServiceError("auth.oidc_http_error", "OIDC 서버와 통신하지 못했습니다.", 502) from exc
    access_token = token_data.get("access_token")
    if not access_token:
        raise AuthServiceError("auth.oidc_invalid_response", "토큰 응답에 access_token 이 없습니다.", 502)
    email_claim = config.email_claim or "email"
    email = userinfo.get(email_claim) or userinfo.get("email") or userinfo.get("preferred_username")
    if not email:
        raise AuthServiceError("auth.oidc_missing_email", "사용자 정보에 이메일이 없습니다.", 400)
    raw_role = (userinfo.get(config.role_claim or "role") or "").strip().lower()
    mapped_role = config.role_mapping.get(raw_role, raw_role)
    rbac_role = _normalize_rbac_role_value(mapped_role, default=config.default_role)
    user_role = "admin" if raw_role in {"admin", "owner"} else "user"
    if payload.get("returnTo"):
        userinfo.setdefault("returnTo", payload.get("returnTo"))
    identity = SsoIdentity(
        provider="oidc",
        email=email,
        display_name=userinfo.get(config.name_claim or "name") or userinfo.get("given_name"),
        external_id=str(userinfo.get("sub") or userinfo.get("id") or ""),
        plan_tier=userinfo.get(config.plan_claim or "plan") or config.default_plan_tier,
        user_role=user_role,
        org_id=userinfo.get("orgId"),
        org_slug=userinfo.get(config.org_claim or "org") or payload.get("orgSlug") or config.default_org_slug,
        org_name=userinfo.get("orgName"),
        rbac_role=rbac_role,
        attributes=userinfo,
    )
    return _complete_sso_login(
        session,
        identity=identity,
        default_plan=config.default_plan_tier,
        default_org_slug=payload.get("orgSlug") or config.default_org_slug,
        auto_provision_org=config.auto_provision_orgs,
        default_rbac_role=config.default_role,
        context=context,
    )


def _normalize_email(email: str) -> str:
    value = (email or "").strip().lower()
    if not value:
        raise AuthServiceError("auth.invalid_payload", "이메일이 필요합니다.", 400)
    return value


def _normalize_signup_channel(channel: Optional[str]) -> SignupChannel:
    candidate = (channel or DEFAULT_SIGNUP_CHANNEL).strip().lower()
    normalized = candidate if candidate in ALLOWED_SIGNUP_CHANNELS else DEFAULT_SIGNUP_CHANNEL
    return cast(SignupChannel, normalized)


def _validate_password_strength(password: str) -> None:
    value = password or ""
    if len(value) < _PASSWORD_MIN_LENGTH:
        raise AuthServiceError(
            "auth.invalid_password",
            f"비밀번호는 최소 {_PASSWORD_MIN_LENGTH}자 이상이어야 합니다. 요구사항: {_PASSWORD_POLICY_DESCRIPTION}",
            400,
        )
    if _PASSWORD_REQUIRE_UPPER and not _UPPER_REGEX.search(value):
        raise AuthServiceError("auth.invalid_password", f"비밀번호에 대문자가 포함되어야 합니다. 요구사항: {_PASSWORD_POLICY_DESCRIPTION}", 400)
    if _PASSWORD_REQUIRE_LOWER and not _LOWER_REGEX.search(value):
        raise AuthServiceError("auth.invalid_password", f"비밀번호에 소문자가 포함되어야 합니다. 요구사항: {_PASSWORD_POLICY_DESCRIPTION}", 400)
    if _PASSWORD_REQUIRE_DIGIT and not _DIGIT_REGEX.search(value):
        raise AuthServiceError("auth.invalid_password", f"비밀번호에 숫자가 포함되어야 합니다. 요구사항: {_PASSWORD_POLICY_DESCRIPTION}", 400)
    if _PASSWORD_REQUIRE_SYMBOL and not _SYMBOL_REGEX.search(value):
        raise AuthServiceError("auth.invalid_password", f"비밀번호에 특수문자가 포함되어야 합니다. 요구사항: {_PASSWORD_POLICY_DESCRIPTION}", 400)


def _hash_password(password: str) -> str:
    _validate_password_strength(password)
    return _PASSWORD_HASHER.hash(password)


def _hash_user_agent(user_agent: Optional[str]) -> Optional[str]:
    if not user_agent:
        return None
    return hashlib.sha256(user_agent.encode("utf-8")).hexdigest()


def _safe_ip_value(ip_value: Optional[str]) -> Optional[str]:
    if not ip_value:
        return None
    try:
        ipaddress.ip_address(ip_value)
        return ip_value
    except ValueError:
        return None


def _handle_failed_attempt(session: Session, user: Optional[Dict[str, Any]], context: RequestContext, now: datetime) -> None:
    if not user:
        return
    attempts = int(user.get("failed_attempts") or 0) + 1
    locked_until = None
    if attempts >= _LOGIN_FAILURE_LIMIT:
        locked_until = now + timedelta(seconds=_ACCOUNT_LOCK_SECONDS)
    session.execute(
        text(
            """
            UPDATE "users"
            SET failed_attempts = :attempts,
                locked_until = :locked_until
            WHERE id = :id
            """
        ),
        {"attempts": attempts, "locked_until": locked_until, "id": user["id"]},
    )
    event = "lock" if locked_until else "login_failed"
    _record_audit_event(
        session,
        event_type=event,
        user_id=str(user["id"]),
        channel="email",
        context=context,
        metadata={"failedAttempts": attempts},
    )
    if locked_until:
        try:
            send_account_locked_email(
                email=user.get("email") or "",
                unlock_after_minutes=max(_ACCOUNT_LOCK_SECONDS // 60, 1),
            )
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Failed to send account lock email: %s", exc, exc_info=True)


def _revoke_expired_sessions(session: Session, user_id: Optional[str]) -> None:
    if not user_id:
        return
    session.execute(
        text(
            """
            UPDATE session_tokens
            SET revoked_at = COALESCE(revoked_at, NOW())
            WHERE user_id = :user_id
              AND revoked_at IS NULL
              AND expires_at < NOW()
            """
        ),
        {"user_id": user_id},
    )


def _record_audit_event(
    session: Session,
    *,
    event_type: str,
    user_id: Optional[str],
    channel: str,
    context: RequestContext,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO audit_auth_events (user_id, event_type, channel, ip, user_agent, metadata)
            VALUES (:user_id, :event_type, :channel, :ip, :user_agent, CAST(:metadata AS JSONB))
            """
        ),
        {
            "user_id": user_id,
            "event_type": event_type,
            "channel": channel,
            "ip": _safe_ip_value(context.ip),
            "user_agent": context.user_agent,
            "metadata": json.dumps(metadata or {}),
        },
    )


def _issue_token_with_audit(
    session: Session,
    *,
    user_id: str,
    token_type: AuthTokenType,
    identifier: str,
    ttl_seconds: int,
    context: RequestContext,
    audit_event: str,
    audit_channel: str = "email",
    audit_metadata: Optional[Dict[str, Any]] = None,
    token_metadata: Optional[Dict[str, Any]] = None,
) -> MagicToken:
    token_meta: Dict[str, Any] = {"ip": context.ip}
    if token_metadata:
        token_meta.update(token_metadata)
    token = issue_magic_token(
        session,
        user_id=user_id,
        token_type=token_type,
        identifier=identifier,
        expires_in=timedelta(seconds=ttl_seconds),
        metadata=token_meta,
    )
    audit_meta = dict(audit_metadata or {})
    audit_meta.setdefault("token_id", token.id)
    _record_audit_event(
        session,
        event_type=audit_event,
        user_id=user_id,
        channel=audit_channel,
        context=context,
        metadata=audit_meta,
    )
    return token


def _enforce_rate_limit(scope: str, identifier: Optional[str], *, limit: int, window_seconds: int) -> None:
    result: RateLimitResult = _check_limit(scope, identifier, limit=limit, window_seconds=window_seconds)  # type: ignore[arg-type]
    if not result.allowed:
        retry_after = max(int((result.reset_at - datetime.now(timezone.utc)).total_seconds()), 1) if result.reset_at else 60
        raise AuthServiceError(
            "auth.rate_limited",
            f"요청이 너무 많습니다. {retry_after}초 후 다시 시도하세요.",
            429,
            extra={"retryAfter": retry_after},
            headers={"Retry-After": str(retry_after)},
        ) from None


def _mark_login_success(session: Session, user_id: str, context: RequestContext, now: datetime) -> None:
    session.execute(
        text(
            """
            UPDATE "users"
            SET failed_attempts = 0,
                locked_until = NULL,
                last_login_at = :now,
                last_login_ip = :ip
            WHERE id = :id
            """
        ),
        {"now": now, "ip": _safe_ip_value(context.ip), "id": user_id},
    )


def _issue_login_result(
    session: Session,
    *,
    user_id: str,
    email: str,
    plan: str,
    role: str,
    email_verified: bool,
    channel: str,
    context: RequestContext,
    now: Optional[datetime] = None,
    remember_me: bool = False,
    onboarding_required: bool = False,
    org_id: Optional[str] = None,
) -> LoginResult:
    current = now or datetime.now(timezone.utc)
    session_uuid = str(uuid.uuid4())
    access_token, access_ttl = create_access_token(
        user_id=user_id,
        email=email,
        plan=plan,
        role=role,
        email_verified=email_verified,
        session_id=session_uuid,
    )
    refresh_jti = str(uuid.uuid4())
    session_token = secrets.token_urlsafe(32)
    refresh_ttl_override = _REMEMBER_REFRESH_TTL if remember_me else None
    refresh_token, refresh_ttl = create_refresh_token(
        user_id=user_id,
        session_id=session_uuid,
        refresh_jti=refresh_jti,
        ttl_seconds=refresh_ttl_override,
    )
    expires_at = current + timedelta(seconds=refresh_ttl)
    metadata_payload = json.dumps({"remember_me": remember_me})
    row = (
        session.execute(
            text(
                """
                INSERT INTO session_tokens (
                    id, user_id, session_token, refresh_jti, device_label, ip, user_agent_hash, expires_at, metadata
                )
                VALUES (
                    :id,
                    :user_id,
                    :session_token,
                    :refresh_jti,
                    :device_label,
                    :ip,
                    :user_agent_hash,
                    :expires_at,
                    CAST(:metadata AS JSONB)
                )
                RETURNING id
                """
            ),
            {
                "id": session_uuid,
                "user_id": user_id,
                "session_token": session_token,
                "refresh_jti": refresh_jti,
                "device_label": channel,
                "ip": _safe_ip_value(context.ip),
                "user_agent_hash": _hash_user_agent(context.user_agent),
                "expires_at": expires_at,
                "metadata": metadata_payload,
            },
        )
        .mappings()
        .first()
    )
    session_id = str(row["id"])
    _record_audit_event(
        session,
        event_type="login_success",
        user_id=user_id,
        channel=channel,
        context=context,
    )
    return LoginResult(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=access_ttl,
        session_id=session_id,
        session_token=session_token,
        user={
            "id": user_id,
            "email": email,
            "plan": plan,
            "role": role,
            "emailVerified": email_verified,
            "orgId": org_id,
        },
        onboarding_required=onboarding_required,
        org_id=org_id,
    )


def _normalize_plan_tier_value(value: Optional[str], *, default: str) -> str:
    fallback = (default or PlanTier.FREE.value).strip().lower()
    candidate = (value or fallback).strip().lower()
    if candidate not in _PLAN_TIER_VALUES:
        return fallback if fallback in _PLAN_TIER_VALUES else PlanTier.FREE.value
    return candidate


def _normalize_user_role_value(value: Optional[str]) -> str:
    candidate = (value or "user").strip().lower()
    if candidate not in _USER_ROLES:
        return "user"
    return candidate


def _normalize_rbac_role_value(value: Optional[str], *, default: str) -> str:
    candidate = (value or default).strip().lower()
    if candidate not in ROLE_ORDER:
        return default
    return candidate


def _ensure_sso_user(
    session: Session,
    *,
    identity: SsoIdentity,
    default_plan: str,
) -> Dict[str, Any]:
    normalized_email = _normalize_email(identity.email)
    now = datetime.now(timezone.utc)
    plan_tier = _normalize_plan_tier_value(identity.plan_tier, default=default_plan)
    app_role = _normalize_user_role_value(identity.user_role)
    existing = (
        session.execute(
            text(
                f"""
                SELECT id, locked_until
                FROM "users"
                WHERE LOWER(email) = :email
                {_FOR_UPDATE}
                """
            ),
            {"email": normalized_email},
        )
        .mappings()
        .first()
    )
    if existing:
        locked_until = existing.get("locked_until")
        if locked_until and locked_until > now:
            raise AuthServiceError("auth.account_locked", "계정이 잠금 상태입니다.", 423)
        row = (
            session.execute(
                text(
                    """
                    UPDATE "users"
                    SET name = COALESCE(:name, name),
                        plan_tier = :plan_tier,
                        role = :role,
                        email_verified_at = COALESCE(email_verified_at, :now)
                    WHERE id = :id
                    RETURNING id, email, plan_tier, role, email_verified_at
                    """
                ),
                {
                    "id": existing["id"],
                    "name": identity.display_name,
                    "plan_tier": plan_tier,
                    "role": app_role,
                    "now": now,
                },
            )
            .mappings()
            .first()
        )
        if not row:
            raise AuthServiceError("auth.sso_update_failed", "사용자 정보를 갱신하지 못했습니다.", 500)
        return row

    row = (
        session.execute(
            text(
                """
                INSERT INTO "users" (email, name, signup_channel, plan_tier, role, email_verified_at, failed_attempts, locked_until)
                VALUES (:email_original, :name, :signup_channel, :plan_tier, :role, :now, 0, NULL)
                RETURNING id, email, plan_tier, role, email_verified_at
                """
            ),
            {
                "email_original": identity.email.strip(),
                "name": identity.display_name,
                "signup_channel": identity.provider,
                "plan_tier": plan_tier,
                "role": app_role,
                "now": now,
            },
        )
        .mappings()
        .first()
    )
    if not row:
        raise AuthServiceError("auth.sso_create_failed", "사용자를 생성하지 못했습니다.", 500)
    return row


def _safe_uuid(value: Optional[str]) -> Optional[uuid.UUID]:
    if not value:
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _lookup_org_by_slug(session: Session, slug: str) -> Optional[uuid.UUID]:
    normalized = slug.strip().lower()
    row = (
        session.execute(
            text(
                """
                SELECT id
                FROM orgs
                WHERE LOWER(slug) = :slug
                LIMIT 1
                """
            ),
            {"slug": normalized},
        )
        .mappings()
        .first()
    )
    return row["id"] if row else None


def _slugify(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = "".join(ch if ch.isalnum() else "-" for ch in value.lower())
    normalized = "-".join(filter(None, normalized.split("-"))).strip("-")
    return normalized[:60] or None


def _create_org(session: Session, slug: Optional[str], name: Optional[str], provider: str) -> uuid.UUID:
    org_id = uuid.uuid4()
    safe_slug = _slugify(slug)
    display_name = (name or slug or f"Workspace {str(org_id)[:8]}").strip()
    session.execute(
        text(
            """
            INSERT INTO orgs (id, name, slug, status, default_role, metadata)
            VALUES (:id, :name, :slug, 'active', 'viewer', CAST(:metadata AS JSONB))
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {
            "id": str(org_id),
            "name": display_name,
            "slug": safe_slug,
            "metadata": json.dumps({"provisionedBy": provider}),
        },
    )
    return org_id


def _bootstrap_workspace(org_id: uuid.UUID, owner_id: uuid.UUID, *, source: str) -> None:
    try:
        bootstrap_workspace_for_org(org_id=org_id, owner_id=owner_id, source=source)
    except Exception:  # pragma: no cover - bootstrap best effort
        logger.warning("Failed to bootstrap workspace for org=%s", org_id, exc_info=True)


def _ensure_default_org(session: Session, user_id: uuid.UUID) -> uuid.UUID:
    existing = (
        session.execute(
            text(
                """
                SELECT org_id
                FROM user_orgs
                WHERE user_id = :user_id
                  AND status = 'active'
                ORDER BY created_at ASC
                LIMIT 1
                """
            ),
            {"user_id": str(user_id)},
        )
        .mappings()
        .first()
    )
    if existing:
        return existing["org_id"]
    org_id = uuid.uuid4()
    session.execute(
        text(
            """
            INSERT INTO orgs (id, name, status, default_role)
            VALUES (:id, :name, 'active', 'viewer')
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id": str(org_id), "name": f"Workspace {str(user_id)[:8]}"},
    )
    session.execute(
        text(
            """
            INSERT INTO user_orgs (org_id, user_id, role_key, status, invited_by, invited_at, accepted_at)
            VALUES (:org_id, :user_id, 'admin', 'active', :user_id, NOW(), NOW())
            ON CONFLICT (org_id, user_id) DO NOTHING
            """
        ),
        {"org_id": str(org_id), "user_id": str(user_id)},
    )
    audit_rbac_event(
        action="rbac.org.bootstrap",
        actor=str(user_id),
        org_id=org_id,
        target_id=str(user_id),
        extra={"source": "sso"},
    )
    _bootstrap_workspace(org_id, user_id, source="auth.ensure_default_org")
    return org_id


def _ensure_membership_for_user(
    session: Session,
    *,
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    rbac_role: str,
) -> None:
    normalized_role = _normalize_rbac_role_value(rbac_role, default="viewer")
    session.execute(
        text(
            """
            INSERT INTO user_orgs (org_id, user_id, role_key, status, invited_by, invited_at, accepted_at)
            VALUES (:org_id, :user_id, :role_key, 'active', :user_id, NOW(), NOW())
            ON CONFLICT (org_id, user_id) DO UPDATE SET
                role_key = EXCLUDED.role_key,
                status = 'active',
                accepted_at = COALESCE(user_orgs.accepted_at, EXCLUDED.accepted_at),
                updated_at = NOW()
            """
        ),
        {"org_id": str(org_id), "user_id": str(user_id), "role_key": normalized_role},
    )
    audit_rbac_event(
        action="rbac.membership.upsert",
        actor=str(user_id),
        org_id=org_id,
        target_id=str(user_id),
        extra={"role": normalized_role, "source": "sso"},
    )


def _ensure_org_subscription(org_id: uuid.UUID, plan_slug: Optional[str], *, source: str) -> None:
    """Ensure an org_subscriptions row exists for ``org_id``."""

    slug = _normalize_plan_tier_value(plan_slug, default="free")
    try:
        entitlement_service.sync_subscription_from_billing(
            org_id=org_id,
            plan_slug=slug,
            status="active",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
            metadata={"source": source},
        )
    except Exception:  # pragma: no cover - best-effort sync
        logger.warning("Failed to bootstrap subscription for org=%s via %s.", org_id, source)


def _ensure_org_target(
    session: Session,
    *,
    user_id: uuid.UUID,
    identity: SsoIdentity,
    default_slug: Optional[str],
    auto_provision: bool,
) -> uuid.UUID:
    if identity.org_id:
        parsed = _safe_uuid(identity.org_id)
        if not parsed:
            raise AuthServiceError("auth.sso.org_invalid", "잘못된 조직 ID 입니다.", 400)
        row = (
            session.execute(
                text("SELECT id FROM orgs WHERE id = :id"),
                {"id": str(parsed)},
            )
            .mappings()
            .first()
        )
        if not row:
            raise AuthServiceError("auth.sso.org_not_found", "조직을 찾을 수 없습니다.", 404)
        return parsed
    slug_candidate = identity.org_slug or default_slug
    if slug_candidate:
        existing = _lookup_org_by_slug(session, slug_candidate)
        if existing:
            return existing
        if auto_provision:
            return _create_org(session, slug_candidate, identity.org_name, identity.provider)
        raise AuthServiceError("auth.sso.org_not_found", f"'{slug_candidate}' 조직이 없습니다.", 404)
    return _ensure_default_org(session, user_id)


def _complete_sso_login(
    session: Session,
    *,
    identity: SsoIdentity,
    default_plan: str,
    default_org_slug: Optional[str],
    auto_provision_org: bool,
    default_rbac_role: str,
    context: RequestContext,
) -> LoginResult:
    now = datetime.now(timezone.utc)
    org_uuid: Optional[uuid.UUID] = None
    plan_slug: Optional[str] = None
    with session.begin():
        user_row = _ensure_sso_user(session, identity=identity, default_plan=default_plan)
        user_uuid = uuid.UUID(str(user_row["id"]))
        org_id = _ensure_org_target(
            session,
            user_id=user_uuid,
            identity=identity,
            default_slug=default_org_slug,
            auto_provision=auto_provision_org,
        )
        org_uuid = org_id
        target_role = identity.rbac_role or default_rbac_role
        _ensure_membership_for_user(session, org_id=org_id, user_id=user_uuid, rbac_role=target_role)
        _mark_login_success(session, str(user_uuid), context, now)
        needs_onboarding = onboarding_service.ensure_first_login_metadata(
            session,
            user_id=str(user_uuid),
        )
        plan_slug = user_row["plan_tier"]
        result = _issue_login_result(
            session,
            user_id=str(user_uuid),
            email=user_row["email"],
            plan=user_row["plan_tier"],
            role=user_row["role"],
            email_verified=bool(user_row.get("email_verified_at")),
            channel=identity.provider,
            context=context,
            now=now,
            onboarding_required=needs_onboarding,
            org_id=str(org_id),
        )
    if org_uuid is not None:
        _ensure_org_subscription(org_uuid, plan_slug, source="auth.sso")
    return result


def _validate_saml_signature(xml_payload: bytes, config: SamlProviderConfig) -> None:
    """Validate XML signatures on the SAML Response or Assertion."""
    cert_pem = _build_pem_certificate(config.idp_certificate)
    if not cert_pem:
        raise AuthServiceError(
            "auth.saml_certificate_missing",
            "IdP 인증서가 설정되지 않아 SAML 서명을 검증할 수 없습니다.",
            500,
        )
    try:
        root = etree.fromstring(xml_payload)
    except etree.XMLSyntaxError as exc:
        raise AuthServiceError("auth.saml_invalid_payload", "SAML 응답을 파싱할 수 없습니다.", 400) from exc
    verifier = XMLVerifier()
    try:
        verifier.verify(root, x509_cert=cert_pem, expect_references=1)
        return
    except InvalidSignature as exc:
        assertion = root.find(".//{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
        has_assertion_signature = (
            assertion is not None
            and assertion.find(".//{http://www.w3.org/2000/09/xmldsig#}Signature") is not None
        )
        if assertion is not None and has_assertion_signature:
            try:
                verifier.verify(assertion, x509_cert=cert_pem, expect_references=1)
                return
            except InvalidSignature as inner_exc:
                exc = inner_exc
        raise AuthServiceError("auth.saml_invalid_signature", "SAML Signature 검증에 실패했습니다.", 400) from exc


def _validate_saml_issue_instant(response: Mapping[str, Any]) -> None:
    raw_issue_instant = response.get("@IssueInstant") or response.get("IssueInstant")
    issued_at = _parse_saml_instant(raw_issue_instant)
    if not issued_at:
        return
    now = datetime.now(timezone.utc)
    skew = timedelta(seconds=_SAML_CLOCK_SKEW_SECONDS)
    if issued_at - skew > now:
        raise AuthServiceError(
            "auth.saml_issueinstant_invalid",
            "Response IssueInstant가 시스템 시간과 일치하지 않습니다.",
            400,
        )


def _enforce_saml_temporal_conditions(conditions: Optional[Mapping[str, Any]]) -> None:
    if not isinstance(conditions, Mapping):
        return
    skew = timedelta(seconds=_SAML_CLOCK_SKEW_SECONDS)
    now = datetime.now(timezone.utc)
    not_before_raw = conditions.get("@NotBefore") or conditions.get("NotBefore")
    not_on_or_after_raw = conditions.get("@NotOnOrAfter") or conditions.get("NotOnOrAfter")
    not_before = _parse_saml_instant(not_before_raw)
    if not_before and now + skew < not_before:
        raise AuthServiceError("auth.saml_not_yet_valid", "Assertion이 아직 유효하지 않습니다.", 400)
    not_on_or_after = _parse_saml_instant(not_on_or_after_raw)
    if not_on_or_after and now - skew >= not_on_or_after:
        raise AuthServiceError("auth.saml_expired", "Assertion 유효기간이 만료되었습니다.", 400)


def _validate_saml_issuer(value: Optional[str], config: SamlProviderConfig, *, source: str) -> None:
    if not value or not config.idp_entity_id:
        return
    issuer = value.strip()
    if issuer != config.idp_entity_id:
        raise AuthServiceError(
            "auth.saml_issuer_mismatch",
            f"{source} Issuer가 구성된 IdP와 일치하지 않습니다.",
            403,
        )


def _parse_saml_instant(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _encode_state(payload: Mapping[str, Any]) -> str:
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    signature = hmac.new(_SSO_STATE_SECRET.encode("utf-8"), serialized.encode("utf-8"), hashlib.sha256).hexdigest()
    blob = json.dumps({"p": payload, "s": signature}, separators=(",", ":"), sort_keys=True)
    return base64.urlsafe_b64encode(blob.encode("utf-8")).decode("utf-8").rstrip("=")


def _decode_state(token: str) -> Mapping[str, Any]:
    padding = "=" * (-len(token) % 4)
    try:
        raw = base64.urlsafe_b64decode(token + padding).decode("utf-8")
        parsed = json.loads(raw)
    except (ValueError, binascii.Error):
        raise AuthServiceError("auth.oidc_invalid_state", "상태 토큰이 손상되었습니다.", 400) from None
    payload = parsed.get("p") or {}
    signature = parsed.get("s")
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    expected = hmac.new(_SSO_STATE_SECRET.encode("utf-8"), serialized.encode("utf-8"), hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        raise AuthServiceError("auth.oidc_invalid_state", "상태 토큰이 유효하지 않습니다.", 400)
    expires_at = payload.get("exp")
    if expires_at and int(expires_at) < int(datetime.now(timezone.utc).timestamp()):
        raise AuthServiceError("auth.oidc_state_expired", "상태 토큰이 만료되었습니다.", 400)
    return payload


def decode_oidc_state(token: str) -> Mapping[str, Any]:
    """Expose decoding for callers that need to inspect OIDC state before login."""

    return _decode_state(token)


def _sanitize_certificate(pem_value: Optional[str]) -> Optional[str]:
    if not pem_value:
        return None
    lines = []
    for line in pem_value.strip().splitlines():
        stripped = line.strip()
        if "BEGIN CERTIFICATE" in stripped or "END CERTIFICATE" in stripped:
            continue
        if stripped:
            lines.append(stripped)
    return "".join(lines) or None


def _build_pem_certificate(pem_value: Optional[str]) -> Optional[str]:
    body = _sanitize_certificate(pem_value)
    if not body:
        return None
    wrapped = "\n".join(textwrap.wrap(body, 64)) or body
    return f"-----BEGIN CERTIFICATE-----\n{wrapped}\n-----END CERTIFICATE-----"


def _extract_first(obj: Optional[Mapping[str, Any]], keys: Sequence[str]) -> Optional[Any]:
    if not obj:
        return None
    for key in keys:
        value = obj.get(key)
        if value is not None:
            return value
    return None


def _coerce_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _coerce_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dict):
        if "#text" in value:
            return str(value["#text"])
        if "value" in value:
            return str(value["value"])
    return str(value)


def _extract_attribute_map(statement: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not statement:
        return {}
    attributes = statement.get("saml:Attribute") or statement.get("Attribute")
    items = _coerce_list(attributes)
    result: Dict[str, Any] = {}
    for item in items:
        if not isinstance(item, Mapping):
            continue
        name = (
            item.get("@Name")
            or item.get("Name")
            or item.get("@FriendlyName")
            or item.get("FriendlyName")
        )
        if not name:
            continue
        values = item.get("saml:AttributeValue") or item.get("AttributeValue")
        value_list = _coerce_list(values)
        text_value = _coerce_text(value_list[0]) if value_list else None
        result[str(name)] = text_value
    return result


def _extract_name_id(assertion: Mapping[str, Any]) -> Optional[str]:
    subject = _extract_first(assertion, ["saml:Subject", "Subject"])
    name_id = _extract_first(subject, ["saml:NameID", "NameID"]) if subject else None
    return _coerce_text(name_id)


__all__ = [
    "AuthServiceError",
    "AccountUnlockConfirmResult",
    "AccountUnlockRequestResult",
    "EmailVerifyResult",
    "LoginResult",
    "PasswordResetConfirmResult",
    "PasswordResetRequestResult",
    "RegisterResult",
    "RequestContext",
    "SessionRefreshResult",
    "VerificationResendResult",
    "confirm_account_unlock",
    "confirm_password_reset",
    "login_user",
    "logout_session",
    "request_account_unlock",
    "refresh_session",
    "register_user",
    "request_password_reset",
    "resend_verification_email",
    "verify_email",
    "generate_saml_metadata",
    "consume_saml_assertion",
    "build_oidc_authorize_url",
    "complete_oidc_login",
]
