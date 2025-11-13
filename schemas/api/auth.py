"""Pydantic schemas for credential 기반 인증 API."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field

from core.auth.constants import DEFAULT_SIGNUP_CHANNEL, SignupChannel

AuthErrorCode = Literal[
    "auth.email_taken",
    "auth.invalid_password",
    "auth.invalid_credentials",
    "auth.invalid_payload",
    "auth.already_verified",
    "auth.needs_verification",
    "auth.account_locked",
    "auth.unlock_not_required",
    "auth.rate_limited",
    "auth.token_expired",
    "auth.token_consumed",
    "auth.token_invalid",
    "auth.user_not_found",
    "auth.session_invalid",
    "auth.session_expired",
]


class RegisterRequest(BaseModel):
    email: EmailStr = Field(..., description="가입 이메일 주소.")
    password: str = Field(..., min_length=8, description="비밀번호(Argon2 해시 대상).")
    name: Optional[str] = Field(default=None, max_length=200, description="표시 이름.")
    acceptTerms: bool = Field(default=False, description="약관 동의 여부.")
    signupChannel: SignupChannel = Field(
        default=DEFAULT_SIGNUP_CHANNEL,
        description="가입 채널 표시값(허용 값: email/google/kakao/naver/admin_invite).",
    )


class RegisterResponse(BaseModel):
    userId: str
    requiresVerification: bool = True
    verificationExpiresIn: int = Field(..., description="이메일 검증 토큰 TTL(초 단위).")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    rememberMe: bool = False
    mfaCode: Optional[str] = None


class AuthUserSchema(BaseModel):
    id: str
    email: EmailStr
    plan: str
    role: str
    emailVerified: bool


class LoginResponse(BaseModel):
    accessToken: str
    refreshToken: str
    expiresIn: int
    sessionId: str
    sessionToken: str
    user: AuthUserSchema


class OidcAuthorizeResponse(BaseModel):
    authorizationUrl: str
    state: str
    expiresIn: int


class EmailVerifyRequest(BaseModel):
    token: str


class EmailVerifyResponse(BaseModel):
    emailVerified: bool
    redirectUrl: Optional[str] = None


class EmailVerifyResendRequest(BaseModel):
    email: EmailStr


class EmailVerifyResendResponse(BaseModel):
    sent: bool


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetResponse(BaseModel):
    sent: bool
    cooldownSeconds: Optional[int] = None


class PasswordResetConfirmRequest(BaseModel):
    token: str
    newPassword: str


class PasswordResetConfirmResponse(BaseModel):
    success: bool


class SessionRefreshRequest(BaseModel):
    refreshToken: str
    sessionId: str
    sessionToken: str


class SessionRefreshResponse(BaseModel):
    accessToken: str
    refreshToken: str
    expiresIn: int


class LogoutRequest(BaseModel):
    sessionId: str
    refreshToken: Optional[str] = None
    allDevices: bool = False


class AccountUnlockRequest(BaseModel):
    email: EmailStr


class AccountUnlockResponse(BaseModel):
    sent: bool


class AccountUnlockConfirmRequest(BaseModel):
    token: str


class AccountUnlockConfirmResponse(BaseModel):
    unlocked: bool
