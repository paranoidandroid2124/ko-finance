"""Auth service submodule exports."""

from __future__ import annotations

from .common import (
    AccountUnlockConfirmResult,
    AccountUnlockRequestResult,
    AuthServiceError,
    EmailVerifyResult,
    LoginResult,
    OidcAuthorizeResult,
    PasswordResetConfirmResult,
    PasswordResetRequestResult,
    RegisterResult,
    RateLimitResult,
    RequestContext,
    SessionRefreshResult,
    VerificationResendResult,
)
from .password import login_user, logout_session, refresh_session, register_user
from .sso import build_oidc_authorize_url, complete_oidc_login, consume_saml_assertion, generate_saml_metadata
from .tokens import (
    confirm_account_unlock,
    confirm_password_reset,
    request_account_unlock,
    request_password_reset,
    resend_verification_email,
    verify_email,
)

__all__ = [
    "AccountUnlockConfirmResult",
    "AccountUnlockRequestResult",
    "AuthServiceError",
    "EmailVerifyResult",
    "LoginResult",
    "OidcAuthorizeResult",
    "PasswordResetConfirmResult",
    "PasswordResetRequestResult",
    "RegisterResult",
    "RateLimitResult",
    "RequestContext",
    "SessionRefreshResult",
    "VerificationResendResult",
    "build_oidc_authorize_url",
    "complete_oidc_login",
    "confirm_account_unlock",
    "confirm_password_reset",
    "consume_saml_assertion",
    "generate_saml_metadata",
    "login_user",
    "logout_session",
    "refresh_session",
    "register_user",
    "request_account_unlock",
    "request_password_reset",
    "resend_verification_email",
    "verify_email",
]
