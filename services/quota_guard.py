"""Shared helper for consuming plan quotas outside the web layer."""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from services.entitlement_service import EntitlementDecision, EntitlementServiceError, entitlement_service
from services.id_utils import resolve_subject

logger = logging.getLogger(__name__)

UUIDLike = Optional[uuid.UUID]


def evaluate_quota(
    action: str,
    *,
    user_id: Any,
    org_id: Any,
    cost: int = 1,
    context: Optional[str] = None,
) -> Optional[EntitlementDecision]:
    """Evaluate quota consumption without enforcing any outcome."""

    subject = resolve_subject(user_id, org_id)
    if subject is None:
        logger.debug("Skipping quota evaluation for %s: no subject context.", action)
        return None

    user_uuid, org_uuid = subject
    try:
        decision: EntitlementDecision = entitlement_service.consume(
            action=action,
            cost=max(cost, 1),
            user_id=user_uuid,
            org_id=org_uuid,
        )
        return decision
    except EntitlementServiceError as exc:
        logger.warning(
            "EntitlementService unavailable (%s) for action=%s: %s",
            context or "quota",
            action,
            exc,
        )
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to evaluate entitlement for action=%s: %s", action, exc)
        return None


def consume_quota(
    action: str,
    *,
    user_id: Any,
    org_id: Any,
    cost: int = 1,
    context: Optional[str] = None,
    extra: Optional[dict[str, Any]] = None,
) -> bool:
    """
    Consume the quota for ``action`` in non-HTTP contexts.

    Returns ``True`` when the action is allowed or when insufficient context is
    provided (best-effort). ``False`` indicates the quota was exhausted.
    """

    decision = evaluate_quota(action, user_id=user_id, org_id=org_id, cost=cost, context=context)
    if decision is None or decision.allowed or decision.backend_error:
        return True

    log_extra = {
        "action": action,
        "context": context or "worker",
        "remaining": decision.remaining,
        "limit": decision.limit,
    }
    if extra:
        log_extra.update(extra)
    logger.info("quota.blocked", extra=log_extra)
    return False


__all__ = ["consume_quota", "evaluate_quota"]
