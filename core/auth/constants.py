"""Centralized constants for authentication flows."""

from __future__ import annotations

from typing import FrozenSet, Literal

SignupChannel = Literal["email", "google", "kakao", "naver", "admin_invite"]
AuthTokenType = Literal["email_verify", "password_reset", "email_change", "account_unlock"]

ALLOWED_SIGNUP_CHANNELS: FrozenSet[SignupChannel] = frozenset(
    ["email", "google", "kakao", "naver", "admin_invite"]
)
DEFAULT_SIGNUP_CHANNEL: SignupChannel = "email"
AUTH_TOKEN_TYPES: FrozenSet[AuthTokenType] = frozenset(
    ["email_verify", "password_reset", "email_change", "account_unlock"]
)

__all__ = [
    "ALLOWED_SIGNUP_CHANNELS",
    "AuthTokenType",
    "AUTH_TOKEN_TYPES",
    "DEFAULT_SIGNUP_CHANNEL",
    "SignupChannel",
]
