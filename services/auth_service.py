"""이메일·비밀번호 인증 서비스 로직."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, cast

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.auth.constants import ALLOWED_SIGNUP_CHANNELS, DEFAULT_SIGNUP_CHANNEL, SignupChannel
from core.env import env_int
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
from services.email_service import (
    send_account_locked_email,
    send_account_unlock_email,
    send_password_reset_email,
    send_verification_email,
)

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

_ARGON_TIME_COST = env_int("AUTH_ARGON2_TIME_COST", 4, minimum=1)
_ARGON_MEMORY_COST = env_int("AUTH_ARGON2_MEMORY_COST", 131072, minimum=8192)
_ARGON_PARALLELISM = env_int("AUTH_ARGON2_PARALLELISM", 1, minimum=1)
_EMAIL_VERIFY_TTL = env_int("AUTH_EMAIL_VERIFY_TTL_SECONDS", 30 * 60, minimum=60)
_PASSWORD_RESET_TTL = env_int("AUTH_PASSWORD_RESET_TTL_SECONDS", 30 * 60, minimum=60)
_LOGIN_FAILURE_LIMIT = env_int("AUTH_LOGIN_FAILURE_LIMIT", 5, minimum=3)
_ACCOUNT_LOCK_SECONDS = env_int("AUTH_ACCOUNT_LOCK_SECONDS", 15 * 60, minimum=60)
_ACCOUNT_UNLOCK_TTL = env_int("AUTH_ACCOUNT_UNLOCK_TTL_SECONDS", 15 * 60, minimum=60)

_PASSWORD_HASHER = PasswordHasher(
    time_cost=_ARGON_TIME_COST,
    memory_cost=_ARGON_MEMORY_COST,
    parallelism=_ARGON_PARALLELISM,
    hash_len=32,
    salt_len=16,
)

@dataclass(frozen=True)
class RequestContext:
    ip: Optional[str]
    user_agent: Optional[str]


@dataclass(frozen=True)
class RegisterResult:
    user_id: str
    verification_expires_in: int


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    refresh_token: str
    expires_in: int
    session_id: str
    session_token: str
    user: Dict[str, Any]


@dataclass(frozen=True)
class EmailVerifyResult:
    email_verified: bool


@dataclass(frozen=True)
class PasswordResetRequestResult:
    sent: bool
    cooldown_seconds: Optional[int]


@dataclass(frozen=True)
class PasswordResetConfirmResult:
    success: bool


@dataclass(frozen=True)
class SessionRefreshResult:
    access_token: str
    refresh_token: str
    expires_in: int


@dataclass(frozen=True)
class VerificationResendResult:
    sent: bool


@dataclass(frozen=True)
class AccountUnlockRequestResult:
    sent: bool


@dataclass(frozen=True)
class AccountUnlockConfirmResult:
    unlocked: bool


class AuthServiceError(RuntimeError):
    """비즈니스 로직 오류를 HTTP 오류로 전달하기 위한 예외."""

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


def register_user(session: Session, payload: Dict[str, Any], *, context: RequestContext) -> RegisterResult:
    raw_email = (payload.get("email") or "").strip()
    email = _normalize_email(raw_email)
    if not payload.get("acceptTerms"):
        raise AuthServiceError("auth.invalid_payload", "약관 동의가 필요합니다.", 400)
    _enforce_rate_limit("auth.register.ip", context.ip, limit=5, window_seconds=600)
    _enforce_rate_limit("auth.register.email", email, limit=3, window_seconds=3600)

    name = (payload.get("name") or "").strip() or None
    signup_channel = _normalize_signup_channel(payload.get("signupChannel"))
    hashed = _hash_password(payload["password"])
    now = datetime.now(timezone.utc)
    verification_token_value: Optional[str] = None

    with session.begin():
        existing = session.execute(
            text(
                """
                SELECT id, password_hash
                FROM "users"
                WHERE LOWER(email) = :email
                FOR UPDATE
                """
            ),
            {"email": email},
        ).mappings().first()

        if existing:
            if existing["password_hash"]:
                raise AuthServiceError("auth.email_taken", "이미 가입된 이메일입니다.", 409)
            user_id = str(existing["id"])
            session.execute(
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
                    "signup_channel": signup_channel,
                    "id": user_id,
                    "now": now,
                },
            )
        else:
            row = session.execute(
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
                    "email_original": payload["email"].strip(),
                    "name": name,
                    "password_hash": hashed,
                    "signup_channel": signup_channel,
                },
            ).mappings().first()
            user_id = str(row["id"])

        token = _issue_token_with_audit(
            session,
            user_id=user_id,
            token_type="email_verify",
            identifier=email,
            ttl_seconds=_EMAIL_VERIFY_TTL,
            context=context,
            audit_event="register",
            audit_channel=signup_channel,
        )
        verification_token_value = token.token
    send_verification_email(email=raw_email or email, token=verification_token_value or "", name=name)
    return RegisterResult(user_id=user_id, verification_expires_in=_EMAIL_VERIFY_TTL)


def login_user(session: Session, payload: Dict[str, Any], *, context: RequestContext) -> LoginResult:
    email = _normalize_email(payload.get("email", ""))
    _enforce_rate_limit("auth.login.ip", context.ip, limit=10, window_seconds=300)
    _enforce_rate_limit("auth.login.email", email, limit=5, window_seconds=300)

    remember_me = bool(payload.get("rememberMe"))
    password = payload.get("password") or ""
    now = datetime.now(timezone.utc)

    with session.begin():
        user = session.execute(
            text(
                """
                SELECT
                    id, email, password_hash, plan_tier, role,
                    email_verified_at, failed_attempts, locked_until
                FROM "users"
                WHERE LOWER(email) = :email
                FOR UPDATE
                """
            ),
            {"email": email},
        ).mappings().first()

        if not user or not user["password_hash"]:
            _handle_failed_attempt(session, user, context, now)
            raise AuthServiceError("auth.invalid_credentials", "이메일 또는 비밀번호가 올바르지 않습니다.", 401)

        if user["locked_until"] and user["locked_until"] > now:
            raise AuthServiceError("auth.account_locked", "계정이 잠겨있습니다. 잠시 후 다시 시도하세요.", 423)

        try:
            _PASSWORD_HASHER.verify(user["password_hash"], password)
        except VerifyMismatchError:
            _handle_failed_attempt(session, user, context, now)
            raise AuthServiceError("auth.invalid_credentials", "이메일 또는 비밀번호가 올바르지 않습니다.", 401)

        if not user["email_verified_at"]:
            raise AuthServiceError("auth.needs_verification", "이메일 인증이 필요합니다.", 403)

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
        {"now": now, "ip": _safe_ip_value(context.ip), "id": user["id"]},
        )

        access_token, access_ttl = create_access_token(
            user_id=str(user["id"]),
            email=user["email"],
            plan=user["plan_tier"],
            role=user["role"],
            email_verified=bool(user["email_verified_at"]),
        )

        refresh_jti = str(uuid.uuid4())
        session_token = secrets.token_urlsafe(32)
        session_uuid = str(uuid.uuid4())

        refresh_token, refresh_ttl = create_refresh_token(
            user_id=str(user["id"]),
            session_id=session_uuid,
            refresh_jti=refresh_jti,
        )

        expires_at = now + timedelta(seconds=refresh_ttl)
        row = session.execute(
            text(
                """
                INSERT INTO session_tokens (
                    id, user_id, session_token, refresh_jti, device_label, ip, user_agent_hash, expires_at
                )
                VALUES (:id, :user_id, :session_token, :refresh_jti, :device_label, :ip, :user_agent_hash, :expires_at)
                RETURNING id
                """
            ),
            {
                "id": session_uuid,
                "user_id": user["id"],
                "session_token": session_token,
                "refresh_jti": refresh_jti,
                "device_label": "web",
                "ip": _safe_ip_value(context.ip),
                "user_agent_hash": _hash_user_agent(context.user_agent),
                "expires_at": expires_at,
            },
        ).mappings().first()
        session_id = str(row["id"])

        _record_audit_event(
            session,
            event_type="login_success",
            user_id=str(user["id"]),
            channel="email",
            context=context,
        )

    return LoginResult(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=access_ttl,
        session_id=session_id,
        session_token=session_token,
        user={
            "id": str(user["id"]),
            "email": user["email"],
            "plan": user["plan_tier"],
            "role": user["role"],
            "emailVerified": True,
        },
    )


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
                """
                SELECT id, email, name, email_verified_at
                FROM "users"
                WHERE LOWER(email) = :email
                FOR UPDATE
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
                """
                SELECT id, user_id, session_token, refresh_jti, revoked_at, expires_at
                FROM session_tokens
                WHERE id = :id
                  AND refresh_jti = :refresh_jti
                FOR UPDATE
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

        access_token, access_ttl = create_access_token(
            user_id=str(user["id"]),
            email=user["email"],
            plan=user["plan_tier"],
            role=user["role"],
            email_verified=bool(user["email_verified_at"]),
            session_id=session_id,
        )
        refresh_jti = str(uuid.uuid4())
        new_refresh_token, refresh_ttl = create_refresh_token(
            user_id=str(user["id"]),
            session_id=session_id,
            refresh_jti=refresh_jti,
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
                """
                SELECT id, email, name, locked_until
                FROM "users"
                WHERE LOWER(email) = :email
                FOR UPDATE
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


def _normalize_email(email: str) -> str:
    value = (email or "").strip().lower()
    if not value:
        raise AuthServiceError("auth.invalid_payload", "이메일이 필요합니다.", 400)
    return value


def _normalize_signup_channel(channel: Optional[str]) -> SignupChannel:
    candidate = (channel or DEFAULT_SIGNUP_CHANNEL).strip().lower()
    normalized = candidate if candidate in ALLOWED_SIGNUP_CHANNELS else DEFAULT_SIGNUP_CHANNEL
    return cast(SignupChannel, normalized)


def _hash_password(password: str) -> str:
    if len(password) < 8:
        raise AuthServiceError("auth.invalid_password", "비밀번호는 8자 이상이어야 합니다.", 400)
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
]
