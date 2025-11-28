"""Guest user rate limiting service using IP-based identification."""

from __future__ import annotations

from typing import Optional

from fastapi import Request, HTTPException, status

from services import auth_rate_limiter
from core.env import env_int
from core.logging import get_logger

logger = get_logger(__name__)

# Configuration
GUEST_CHAT_LIMIT = env_int("GUEST_CHAT_LIMIT_PER_HOUR", 10, minimum=1)
GUEST_CHAT_WINDOW_SECONDS = env_int("GUEST_CHAT_WINDOW_SECONDS", 3600, minimum=60)  # 1 hour


def get_client_ip(request: Request) -> str:
    """Extract client IP from request headers with proxy support.
    
    Checks X-Forwarded-For and X-Real-IP headers for proxied requests.
    Falls back to direct client host.
    """
    # Check X-Forwarded-For (can be comma-separated list)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP (client's real IP)
        return forwarded_for.split(",")[0].strip()
    
    # Check X-Real-IP
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    
    # Fallback to direct client
    if request.client:
        return request.client.host
    
    return "unknown"


def check_guest_rate_limit(
    request: Request,
    *,
    limit: Optional[int] = None,
    window_seconds: Optional[int] = None,
) -> None:
    """Check rate limit for guest users based on IP address.
    
    Args:
        request: FastAPI Request object
        limit: Maximum number of requests allowed (defaults to GUEST_CHAT_LIMIT)
        window_seconds: Time window in seconds (defaults to GUEST_CHAT_WINDOW_SECONDS)
    
    Raises:
        HTTPException: If rate limit exceeded
    """
    client_ip = get_client_ip(request)
    actual_limit = limit if limit is not None else GUEST_CHAT_LIMIT
    actual_window = window_seconds if window_seconds is not None else GUEST_CHAT_WINDOW_SECONDS
    
    result = auth_rate_limiter.check_limit(
        scope="guest_chat",
        identifier=client_ip,
        limit=actual_limit,
        window_seconds=actual_window,
    )
    
    if not result.allowed:
        logger.warning(
            "Guest rate limit exceeded for IP %s (limit: %d/%ds)",
            client_ip,
            actual_limit,
            actual_window,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "rate_limit_exceeded",
                "message": f"시간당 무료 체험 한도({actual_limit}회)를 초과했습니다. 잠시 후 다시 시도하거나 회원가입 후 이용해주세요.",
                "remaining": 0,
                "reset_at": result.reset_at.isoformat() if result.reset_at else None,
            },
        )
    
    logger.debug(
        "Guest rate limit check passed for IP %s (remaining: %d)",
        client_ip,
        result.remaining or 0,
    )


__all__ = ["check_guest_rate_limit", "get_client_ip"]
