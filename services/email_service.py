"""Transactional email helpers for auth flows."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from core.env import env_int, env_str
from services import notification_service

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
EMAIL_TEMPLATE_DIR = REPO_ROOT / "templates" / "email"

_ENV: Optional[Environment] = None

BRAND_NAME = env_str("APP_BRAND_NAME") or "Nuvien"
SUPPORT_EMAIL = env_str("SUPPORT_EMAIL") or env_str("ALERT_EMAIL_FROM") or "support@kfinance.ai"
FRONTEND_BASE_URL = (
    env_str("AUTH_FRONTEND_BASE_URL")
    or env_str("FRONTEND_BASE_URL")
    or env_str("NEXTAUTH_URL")
    or "http://localhost:3000"
)


def _get_env() -> Environment:
    global _ENV  # pylint: disable=global-statement
    if _ENV is None:
        _ENV = Environment(
            loader=FileSystemLoader(EMAIL_TEMPLATE_DIR),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _ENV


def _render_template(template: str, context: Dict[str, object]) -> str:
    env = _get_env()
    try:
        return env.get_template(template).render(**context)
    except TemplateNotFound:
        logger.error("Email template %s not found.", template)
        return ""


def _frontend_url(path: str) -> str:
    base = FRONTEND_BASE_URL.rstrip("/")
    fragment = path.lstrip("/")
    return f"{base}/{fragment}"


def _dispatch_email(recipient: str, subject: str, text_body: str, html_body: str) -> None:
    try:
        notification_service.dispatch_notification(
            "email",
            text_body,
            targets=[recipient],
            metadata={
                "subject": subject,
                "html_template": html_body,
            },
        )
    except Exception as exc:  # pragma: no cover - best effort
        logger.warning("Failed to dispatch auth email to %s: %s", recipient, exc, exc_info=True)


def send_verification_email(*, email: str, token: str, name: Optional[str] = None) -> None:
    verify_url = _frontend_url(f"auth/verify/{token}")
    context = {
        "brand_name": BRAND_NAME,
        "verify_url": verify_url,
        "recipient_name": name,
        "support_email": SUPPORT_EMAIL,
    }
    html = _render_template("auth_verification.html.jinja", context)
    text = f"{BRAND_NAME} 이메일 인증 링크\n{verify_url}\n본 요청을 하지 않았다면 지원팀({SUPPORT_EMAIL})에 문의해 주세요."
    _dispatch_email(email, f"[{BRAND_NAME}] 이메일 인증 안내", text, html)


def send_password_reset_email(*, email: str, token: str, name: Optional[str] = None) -> None:
    reset_url = _frontend_url(f"auth/reset/{token}")
    ttl_minutes = env_int("AUTH_PASSWORD_RESET_TTL_SECONDS", 30 * 60, minimum=60) // 60
    context = {
        "brand_name": BRAND_NAME,
        "reset_url": reset_url,
        "recipient_name": name,
        "support_email": SUPPORT_EMAIL,
        "ttl_minutes": ttl_minutes,
    }
    html = _render_template("auth_password_reset.html.jinja", context)
    text = (
        f"{BRAND_NAME} 비밀번호 재설정 안내\n"
        f"새 비밀번호 설정: {reset_url}\n"
        f"요청하지 않았다면 즉시 지원팀({SUPPORT_EMAIL})에 문의해 주세요."
    )
    _dispatch_email(email, f"[{BRAND_NAME}] 비밀번호 재설정", text, html)


def send_account_locked_email(*, email: str, unlock_after_minutes: int) -> None:
    reset_url = _frontend_url("auth/forgot-password")
    context = {
        "brand_name": BRAND_NAME,
        "reset_url": reset_url,
        "support_email": SUPPORT_EMAIL,
        "unlock_minutes": unlock_after_minutes,
    }
    html = _render_template("auth_account_locked.html.jinja", context)
    text = (
        f"{BRAND_NAME} 계정이 일시 잠금되었습니다.\n"
        f"{unlock_after_minutes}분 후 자동으로 풀리며, 비밀번호를 즉시 변경하려면 {reset_url}을 사용하세요."
    )
    _dispatch_email(email, f"[{BRAND_NAME}] 계정 잠금 안내", text, html)


def send_account_unlock_email(*, email: str, token: str, name: Optional[str] = None) -> None:
    unlock_url = _frontend_url(f"auth/unlock/{token}")
    context = {
        "brand_name": BRAND_NAME,
        "unlock_url": unlock_url,
        "recipient_name": name,
        "support_email": SUPPORT_EMAIL,
    }
    html = _render_template("auth_account_unlock.html.jinja", context)
    text = (
        f"{BRAND_NAME} 계정 잠금 해제 링크\n"
        f"잠금 해제: {unlock_url}\n"
        f"잘못된 시도였다면 지원팀({SUPPORT_EMAIL})에 문의해 주세요."
    )
    _dispatch_email(email, f"[{BRAND_NAME}] 계정 잠금 해제", text, html)


__all__ = [
    "send_verification_email",
    "send_password_reset_email",
    "send_account_locked_email",
    "send_account_unlock_email",
]
