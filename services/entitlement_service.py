"""EntitlementService v1 implementation (plans, quotas, and subscription sync)."""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, Mapping, Optional, Union

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.env import env_int, env_str

try:  # pragma: no cover - optional dependency
    import redis  # type: ignore
except ImportError:  # pragma: no cover
    redis = None  # type: ignore

try:  # pragma: no cover - imported lazily for tests
    from database import SessionLocal as _SessionLocal
except Exception:  # pragma: no cover
    _SessionLocal = None

logger = logging.getLogger(__name__)

LimitValue = Union[int, bool]

DEFAULT_PLAN_SLUG = env_str("ENTITLEMENT_DEFAULT_PLAN", "free") or "free"
DEFAULT_PERIOD_DAYS = env_int("ENTITLEMENT_DEFAULT_PERIOD_DAYS", 30, minimum=1)
REDIS_URL = env_str("ENTITLEMENT_REDIS_URL") or env_str("AUTH_RATE_LIMIT_REDIS_URL")
REDIS_PREFIX = env_str("ENTITLEMENT_REDIS_PREFIX", "ent")

DEFAULT_PLAN_LIMITS: Dict[str, Dict[str, LimitValue]] = {
    "free": {
        "alerts.rules.create": 3,
        "watchlist.radar": 6,
        "watchlist.preview": 2,
        "rag.chat": 20,
        "api.chat": 40,
    },
    "starter": {
        "alerts.rules.create": 10,
        "watchlist.radar": 24,
        "watchlist.preview": 6,
        "rag.chat": 80,
        "api.chat": 150,
    },
    "pro": {
        "alerts.rules.create": 50,
        "watchlist.radar": 100,
        "watchlist.preview": 20,
        "rag.chat": 500,
        "api.chat": 400,
    },
    "enterprise": {},
}


@dataclass(frozen=True)
class Entitlements:
    plan: str
    limits: Mapping[str, LimitValue]


@dataclass(frozen=True)
class EntitlementDecision:
    allowed: bool
    remaining: Optional[int]
    limit: Optional[int] = None
    backend_error: bool = False


class EntitlementServiceError(RuntimeError):
    """Raised when entitlement operations cannot proceed."""


class EntitlementService:
    """Centralised entitlement/plan lookup + quota accounting."""

    def __init__(
        self,
        *,
        session_factory: Optional[Callable[[], Session]] = None,
    ) -> None:
        if session_factory is None:
            if _SessionLocal is None:  # pragma: no cover - enforced during runtime
                raise EntitlementServiceError("SessionLocal is unavailable. DATABASE_URL must be configured.")
            session_factory = _SessionLocal

        self._session_factory = session_factory
        self._plan_cache: Dict[str, Dict[str, LimitValue]] = {}
        self._org_plan_cache: Dict[uuid.UUID, str] = {}
        self._cache_lock = threading.Lock()
        self._redis_client: Optional["redis.Redis"] = None  # type: ignore[name-defined]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, *, user_id: uuid.UUID, org_id: uuid.UUID) -> Entitlements:
        """Return plan slug + limit map for the given org/user."""
        plan_slug = self._resolve_plan_slug(org_id)
        limits = self._load_plan_limits(plan_slug)
        return Entitlements(plan=plan_slug, limits=dict(limits))

    def check(self, *, user_id: uuid.UUID, org_id: uuid.UUID, action: str, cost: int = 1) -> EntitlementDecision:
        """Read-only quota check."""
        return self._evaluate(action=action, cost=cost, user_id=user_id, org_id=org_id, mutate=False)

    def consume(self, *, user_id: uuid.UUID, org_id: uuid.UUID, action: str, cost: int = 1) -> EntitlementDecision:
        """Atomically consume quota for ``action``."""
        return self._evaluate(action=action, cost=cost, user_id=user_id, org_id=org_id, mutate=True)

    def sync_subscription_from_billing(
        self,
        *,
        org_id: uuid.UUID,
        plan_slug: str,
        status: str,
        current_period_end: Optional[datetime],
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> None:
        """Upsert subscription rows based on billing webhooks."""
        normalized_slug = plan_slug.strip().lower() or DEFAULT_PLAN_SLUG
        normalized_status = status.strip().lower() or "active"
        effective_period_end = current_period_end or (datetime.now(timezone.utc) + timedelta(days=DEFAULT_PERIOD_DAYS))

        session = self._session_factory()
        try:
            plan_id = self._ensure_plan(session, normalized_slug)
            payload = {
                "org_id": str(org_id),
                "plan_id": plan_id,
                "status": normalized_status,
                "current_period_end": effective_period_end,
                "metadata": metadata or {},
            }
            session.execute(
                text(
                    """
                    INSERT INTO org_subscriptions (org_id, plan_id, status, current_period_end, metadata)
                    VALUES (:org_id, :plan_id, :status, :current_period_end, :metadata::jsonb)
                    ON CONFLICT (org_id)
                    DO UPDATE SET
                        plan_id = EXCLUDED.plan_id,
                        status = EXCLUDED.status,
                        current_period_end = EXCLUDED.current_period_end,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    """,
                ),
                payload,
            )
            session.commit()
            with self._cache_lock:
                self._org_plan_cache.pop(org_id, None)
        except SQLAlchemyError:
            session.rollback()
            logger.exception("Failed to upsert org subscription for org=%s", org_id)
            raise
        finally:
            session.close()

    def invalidate_plan_cache(self, plan_slug: Optional[str] = None) -> None:
        with self._cache_lock:
            if plan_slug:
                self._plan_cache.pop(plan_slug, None)
            else:
                self._plan_cache.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evaluate(
        self,
        *,
        action: str,
        cost: int,
        user_id: uuid.UUID,
        org_id: uuid.UUID,
        mutate: bool,
    ) -> EntitlementDecision:
        if cost <= 0:
            cost = 1
        limits = self.get(user_id=user_id, org_id=org_id).limits
        value = limits.get(action)

        if isinstance(value, bool):
            allowed = bool(value)
            return EntitlementDecision(allowed=allowed, remaining=None, limit=None)

        if value is None:
            return EntitlementDecision(allowed=True, remaining=None, limit=None)

        try:
            limit = int(value)
        except (TypeError, ValueError):
            logger.warning("Invalid entitlement limit for %s=%s. Allowing by default.", action, value)
            return EntitlementDecision(allowed=True, remaining=None, limit=None)

        if limit <= 0:
            return EntitlementDecision(allowed=False, remaining=0, limit=limit)

        if mutate:
            used = self._increment_usage(org_id=org_id, user_id=user_id, action=action, cost=cost)
        else:
            used = self._read_usage(org_id=org_id, user_id=user_id, action=action)

        if used is None:
            logger.warning("Usage backend unavailable for action=%s.", action)
            return EntitlementDecision(allowed=True, remaining=None, limit=limit, backend_error=True)

        remaining = max(limit - used, 0)
        return EntitlementDecision(allowed=remaining >= 0, remaining=remaining, limit=limit)

    def _resolve_plan_slug(self, org_id: uuid.UUID) -> str:
        with self._cache_lock:
            cached = self._org_plan_cache.get(org_id)
            if cached:
                return cached

        session = self._session_factory()
        try:
            result = session.execute(
                text(
                    """
                    SELECT p.slug
                    FROM org_subscriptions os
                    JOIN plans p ON p.id = os.plan_id
                    WHERE os.org_id = :org_id
                      AND os.status IN ('active', 'trialing', 'past_due')
                    ORDER BY os.updated_at DESC
                    LIMIT 1
                    """,
                ),
                {"org_id": str(org_id)},
            )
            slug = result.scalar()
        except SQLAlchemyError:
            logger.exception("Failed to resolve plan slug for org=%s", org_id)
            slug = None
        finally:
            session.close()

        resolved = (slug or DEFAULT_PLAN_SLUG).strip().lower() or DEFAULT_PLAN_SLUG
        with self._cache_lock:
            self._org_plan_cache[org_id] = resolved
        return resolved

    def _load_plan_limits(self, plan_slug: str) -> Mapping[str, LimitValue]:
        normalized = plan_slug.strip().lower() or DEFAULT_PLAN_SLUG
        with self._cache_lock:
            cached = self._plan_cache.get(normalized)
            if cached is not None:
                return cached

        session = self._session_factory()
        try:
            result = session.execute(
                text(
                    """
                    SELECT pe.key, pe.value
                    FROM plan_entitlements pe
                    JOIN plans p ON p.id = pe.plan_id
                    WHERE p.slug = :slug
                    ORDER BY pe.key
                    """,
                ),
                {"slug": normalized},
            )
            rows = result.fetchall()
        except SQLAlchemyError:
            logger.exception("Failed to load plan entitlements for plan=%s", normalized)
            rows = []
        finally:
            session.close()

        limits: Dict[str, LimitValue] = dict(DEFAULT_PLAN_LIMITS.get(normalized, {}))
        for row in rows:
            key = row.key or row[0]
            value = row.value or row[1]
            decoded = self._decode_value(value)
            if decoded is None or not key:
                continue
            limits[str(key)] = decoded

        if not limits:
            logger.warning("Plan %s does not have entitlements configured. Defaulting to empty map.", normalized)

        with self._cache_lock:
            self._plan_cache[normalized] = dict(limits)

        return limits

    @staticmethod
    def _decode_value(value: Any) -> Optional[LimitValue]:
        if value is None:
            return None
        if isinstance(value, (bool, int)):
            return value
        if isinstance(value, dict):
            if "int" in value:
                try:
                    return int(value["int"])
                except (TypeError, ValueError):
                    return None
            if "bool" in value:
                return bool(value["bool"])
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _ensure_plan(self, session: Session, slug: str) -> int:
        result = session.execute(text("SELECT id FROM plans WHERE slug = :slug"), {"slug": slug})
        plan_id = result.scalar()
        if plan_id:
            return int(plan_id)
        name = slug.title()
        result = session.execute(
            text("INSERT INTO plans (slug, name) VALUES (:slug, :name) RETURNING id"),
            {"slug": slug, "name": name},
        )
        plan_id = result.scalar_one()
        session.flush()
        return int(plan_id)

    def _seconds_until_day_end(self) -> int:
        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).date()
        boundary = datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc)
        return max(int((boundary - now).total_seconds()), 60)

    def _redis_key(self, org_id: uuid.UUID, user_id: uuid.UUID, action: str) -> str:
        today = date.today().strftime("%Y%m%d")
        return f"{REDIS_PREFIX}:{today}:{org_id}:{user_id}:{action}"

    def _get_redis(self) -> Optional["redis.Redis"]:  # type: ignore[name-defined]
        if self._redis_client is not None:
            return self._redis_client
        if not REDIS_URL or redis is None:
            return None
        try:
            self._redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=False)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to initialise entitlement Redis: %s", exc)
            self._redis_client = None
        return self._redis_client

    def _read_usage(self, *, org_id: uuid.UUID, user_id: uuid.UUID, action: str) -> Optional[int]:
        client = self._get_redis()
        if client is not None:
            key = self._redis_key(org_id, user_id, action)
            try:
                raw = client.get(key)
                if raw is not None:
                    return int(raw)
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to read entitlement usage from Redis: %s", exc)

        # Fallback to Postgres snapshot
        session = self._session_factory()
        try:
            result = session.execute(
                text(
                    """
                    SELECT used
                    FROM entitlement_usage_daily
                    WHERE org_id = :org_id AND user_id = :user_id AND action = :action AND day = CURRENT_DATE
                    """,
                ),
                {"org_id": str(org_id), "user_id": str(user_id), "action": action},
            )
            value = result.scalar()
            return int(value) if value is not None else 0
        except SQLAlchemyError:
            logger.exception("Failed to read entitlement usage snapshot.")
            return None
        finally:
            session.close()

    def _increment_usage(self, *, org_id: uuid.UUID, user_id: uuid.UUID, action: str, cost: int) -> Optional[int]:
        redis_count = self._increment_usage_redis(org_id=org_id, user_id=user_id, action=action, cost=cost)
        db_count = self._increment_usage_db(org_id=org_id, user_id=user_id, action=action, cost=cost)
        if redis_count is not None:
            return redis_count
        return db_count

    def _increment_usage_redis(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        action: str,
        cost: int,
    ) -> Optional[int]:
        client = self._get_redis()
        if client is None:
            return None
        key = self._redis_key(org_id, user_id, action)
        expire_seconds = self._seconds_until_day_end()
        try:
            pipeline = client.pipeline()
            pipeline.incrby(key, cost)
            pipeline.expire(key, expire_seconds)
            count, _ = pipeline.execute()
            return int(count)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to increment entitlement usage in Redis: %s", exc)
            return None

    def _increment_usage_db(
        self,
        *,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        action: str,
        cost: int,
    ) -> Optional[int]:
        session = self._session_factory()
        try:
            result = session.execute(
                text(
                    """
                    INSERT INTO entitlement_usage_daily (org_id, user_id, action, day, used)
                    VALUES (:org_id, :user_id, :action, CURRENT_DATE, :cost)
                    ON CONFLICT (org_id, user_id, action, day)
                    DO UPDATE SET
                        used = entitlement_usage_daily.used + EXCLUDED.used,
                        updated_at = NOW()
                    RETURNING used
                    """,
                ),
                {"org_id": str(org_id), "user_id": str(user_id), "action": action, "cost": cost},
            )
            value = result.scalar()
            session.commit()
            return int(value) if value is not None else None
        except SQLAlchemyError:
            session.rollback()
            logger.exception("Failed to increment entitlement usage snapshot.")
            return None
        finally:
            session.close()


entitlement_service = EntitlementService()

__all__ = [
    "EntitlementDecision",
    "EntitlementService",
    "EntitlementServiceError",
    "Entitlements",
    "entitlement_service",
]
