"""Plan tier inference helpers, persistence, and feature mapping."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Literal, Mapping, MutableMapping, Optional, Sequence

from fastapi import Request

from core.env import env_str
from services.admin_audit import append_audit_log

logger = logging.getLogger(__name__)

PlanTier = Literal["free", "pro", "enterprise"]

SUPPORTED_PLAN_TIERS: Sequence[str] = ("free", "pro", "enterprise")

PLAN_BASE_ENTITLEMENTS: Mapping[str, frozenset[str]] = {
    "free": frozenset(),
    "pro": frozenset({"search.compare", "search.alerts", "evidence.inline_pdf"}),
    "enterprise": frozenset(
        {
            "search.compare",
            "search.alerts",
            "search.export",
            "evidence.inline_pdf",
            "evidence.diff",
            "timeline.full",
        }
    ),
}


@dataclass(slots=True)
class PlanQuota:
    """Quota presets used by clients when enforcing limits."""

    chat_requests_per_day: Optional[int]
    rag_top_k: Optional[int]
    self_check_enabled: bool
    peer_export_row_limit: Optional[int]

    def to_dict(self) -> MutableMapping[str, Optional[int | bool]]:
        return {
            "chatRequestsPerDay": self.chat_requests_per_day,
            "ragTopK": self.rag_top_k,
            "selfCheckEnabled": self.self_check_enabled,
            "peerExportRowLimit": self.peer_export_row_limit,
        }


PLAN_QUOTA_PRESETS: Mapping[str, PlanQuota] = {
    "free": PlanQuota(chat_requests_per_day=20, rag_top_k=4, self_check_enabled=False, peer_export_row_limit=0),
    "pro": PlanQuota(chat_requests_per_day=500, rag_top_k=6, self_check_enabled=True, peer_export_row_limit=100),
    "enterprise": PlanQuota(
        chat_requests_per_day=None,
        rag_top_k=10,
        self_check_enabled=True,
        peer_export_row_limit=None,
    ),
}


@dataclass(slots=True)
class PersistedPlanSettings:
    """Disk-backed plan defaults maintained through the settings API."""

    plan_tier: PlanTier
    entitlements: tuple[str, ...]
    quota: PlanQuota
    expires_at: Optional[datetime]
    updated_at: datetime
    updated_by: Optional[str]
    change_note: Optional[str]
    checkout_requested: bool = False


@dataclass(slots=True)
class PlanContext:
    """Resolved plan metadata stored on the request."""

    tier: PlanTier
    expires_at: Optional[datetime]
    entitlements: frozenset[str]
    quota: PlanQuota
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    change_note: Optional[str] = None
    checkout_requested: bool = False

    def allows(self, entitlement: str) -> bool:
        return entitlement in self.entitlements

    def feature_flags(self) -> Mapping[str, bool]:
        """Expose consolidated feature flags derived from entitlements."""
        return {
            "search.compare": self.allows("search.compare"),
            "search.alerts": self.allows("search.alerts"),
            "search.export": self.allows("search.export"),
            "evidence.inline_pdf": self.allows("evidence.inline_pdf"),
            "evidence.diff": self.allows("evidence.diff"),
            "timeline.full": self.allows("timeline.full"),
        }


_DEFAULT_PLAN_SETTINGS_PATH = Path("uploads") / "admin" / "plan_settings.json"
_PLAN_SETTINGS_CACHE: Optional[PersistedPlanSettings] = None
_PLAN_SETTINGS_CACHE_PATH: Optional[Path] = None


def _normalize_plan_tier(value: Optional[str]) -> PlanTier:
    if not value:
        return "free"
    lowered = value.strip().lower()
    if lowered in SUPPORTED_PLAN_TIERS:
        return lowered
    return "free"


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _parse_entitlements(raw: Optional[str]) -> set[str]:
    if not raw:
        return set()
    items = {item.strip() for item in raw.split(",")}
    return {item for item in items if item}


def _plan_settings_path() -> Path:
    global _PLAN_SETTINGS_CACHE, _PLAN_SETTINGS_CACHE_PATH
    env_file = env_str("PLAN_SETTINGS_FILE")
    path = Path(env_file) if env_file else _DEFAULT_PLAN_SETTINGS_PATH
    if _PLAN_SETTINGS_CACHE_PATH is not None and _PLAN_SETTINGS_CACHE_PATH != path:
        _PLAN_SETTINGS_CACHE = None
    _PLAN_SETTINGS_CACHE_PATH = path
    return path


def _normalize_actor(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _normalize_note(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _parse_quota_override_string(raw: str) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    for pair in raw.split(","):
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        overrides[key.strip()] = value.strip()
    return overrides


def _coerce_optional_int(field: str, value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} 값은 0 이상의 정수 또는 null이어야 합니다.")
    if isinstance(value, (int, float)):
        candidate = int(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.lower() in {"none", "null"}:
            return None
        candidate = int(text)
    if candidate < 0:
        raise ValueError(f"{field} 값은 음수가 될 수 없습니다.")
    return candidate


def _coerce_bool(field: str, value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value in {0, 0.0}:
            return False
        if value in {1, 1.0}:
            return True
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y"}:
            return True
        if normalized in {"0", "false", "no", "n"}:
            return False
    raise ValueError(f"{field} 값이 올바르지 않습니다.")


def _apply_quota_overrides(base: PlanQuota, overrides: Mapping[str, Any], *, strict: bool = False) -> PlanQuota:
    if not overrides:
        return PlanQuota(
            chat_requests_per_day=base.chat_requests_per_day,
            rag_top_k=base.rag_top_k,
            self_check_enabled=base.self_check_enabled,
            peer_export_row_limit=base.peer_export_row_limit,
        )

    chat = base.chat_requests_per_day
    rag = base.rag_top_k
    self_check = base.self_check_enabled
    peer = base.peer_export_row_limit

    if "chatRequestsPerDay" in overrides:
        try:
            chat = _coerce_optional_int("chatRequestsPerDay", overrides["chatRequestsPerDay"])
        except ValueError as exc:
            if strict:
                raise
            logger.warning("Invalid chatRequestsPerDay override ignored: %s", exc)

    if "ragTopK" in overrides:
        try:
            rag = _coerce_optional_int("ragTopK", overrides["ragTopK"])
        except ValueError as exc:
            if strict:
                raise
            logger.warning("Invalid ragTopK override ignored: %s", exc)

    if "peerExportRowLimit" in overrides:
        try:
            peer = _coerce_optional_int("peerExportRowLimit", overrides["peerExportRowLimit"])
        except ValueError as exc:
            if strict:
                raise
            logger.warning("Invalid peerExportRowLimit override ignored: %s", exc)

    if "selfCheckEnabled" in overrides:
        try:
            self_check = _coerce_bool("selfCheckEnabled", overrides["selfCheckEnabled"])
        except ValueError as exc:
            if strict:
                raise
            logger.warning("Invalid selfCheckEnabled override ignored: %s", exc)

    return PlanQuota(
        chat_requests_per_day=chat,
        rag_top_k=rag,
        self_check_enabled=self_check,
        peer_export_row_limit=peer,
    )


def _load_plan_settings(*, reload: bool = False) -> Optional[PersistedPlanSettings]:
    global _PLAN_SETTINGS_CACHE
    if _PLAN_SETTINGS_CACHE is not None and not reload:
        return _PLAN_SETTINGS_CACHE

    path = _plan_settings_path()
    if not path.exists():
        _PLAN_SETTINGS_CACHE = None
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load plan settings from %s: %s", path, exc)
        _PLAN_SETTINGS_CACHE = None
        return None

    tier = _normalize_plan_tier(payload.get("planTier"))

    ent_raw = payload.get("entitlements") or []
    entitlements: list[str] = []
    seen: set[str] = set()
    for item in ent_raw:
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        entitlements.append(normalized)
        seen.add(normalized)

    quota_payload = payload.get("quota") or {}
    quota = _apply_quota_overrides(
        PLAN_QUOTA_PRESETS.get(tier, PLAN_QUOTA_PRESETS["free"]),
        quota_payload,
        strict=False,
    )

    settings = PersistedPlanSettings(
        plan_tier=tier,
        entitlements=tuple(entitlements),
        quota=quota,
        expires_at=_parse_iso_datetime(payload.get("expiresAt")),
        updated_at=_parse_iso_datetime(payload.get("updatedAt")) or datetime.now(timezone.utc),
        updated_by=_normalize_actor(payload.get("updatedBy")),
        change_note=_normalize_note(payload.get("changeNote")),
        checkout_requested=payload.get("checkoutRequested") is True,
    )
    _PLAN_SETTINGS_CACHE = settings
    return settings


def _store_plan_settings(settings: PersistedPlanSettings) -> None:
    path = _plan_settings_path()
    payload = {
        "planTier": settings.plan_tier,
        "expiresAt": settings.expires_at.isoformat() if settings.expires_at else None,
        "entitlements": list(settings.entitlements),
        "quota": settings.quota.to_dict(),
        "updatedAt": settings.updated_at.isoformat(),
        "updatedBy": settings.updated_by,
        "changeNote": settings.change_note,
        "checkoutRequested": settings.checkout_requested,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)
        logger.info(
            "Plan settings persisted by %s (tier=%s).",
            settings.updated_by or "unknown",
            settings.plan_tier,
        )
        global _PLAN_SETTINGS_CACHE
        _PLAN_SETTINGS_CACHE = settings
    except OSError as exc:
        logger.error("Failed to write plan settings to %s: %s", path, exc)
        raise


def _build_plan_context(
    *,
    header_tier: Optional[str] = None,
    header_entitlements: Optional[str] = None,
    header_expires_at: Optional[str] = None,
    header_quota: Optional[str] = None,
) -> PlanContext:
    settings = _load_plan_settings()
    has_header_override = any(value for value in (header_tier, header_entitlements, header_expires_at, header_quota))

    fallback_tier = (
        settings.plan_tier if settings and not has_header_override else env_str("DEFAULT_PLAN_TIER", "free")
    )
    tier = _normalize_plan_tier(header_tier or fallback_tier)

    env_entitlements = _parse_entitlements(env_str("DEFAULT_PLAN_ENTITLEMENTS", ""))
    header_entitlement_set = _parse_entitlements(header_entitlements)

    if settings and not has_header_override and settings.entitlements:
        entitlements = set(settings.entitlements)
    else:
        entitlements = set(PLAN_BASE_ENTITLEMENTS.get(tier, PLAN_BASE_ENTITLEMENTS["free"]))
    entitlements.update(env_entitlements)
    entitlements.update(header_entitlement_set)

    expires_at: Optional[datetime] = None
    if header_expires_at:
        expires_at = _parse_iso_datetime(header_expires_at)
        if expires_at is None:
            logger.warning("Invalid x-plan-expires-at header ignored: %s", header_expires_at)
    elif settings and not has_header_override and settings.expires_at:
        expires_at = settings.expires_at
    else:
        expires_at = _parse_iso_datetime(env_str("DEFAULT_PLAN_EXPIRES_AT"))

    quota = PLAN_QUOTA_PRESETS.get(tier, PLAN_QUOTA_PRESETS["free"])
    if settings and not has_header_override:
        quota = _apply_quota_overrides(quota, settings.quota.to_dict())

    if header_quota:
        quota = _apply_quota_overrides(quota, _parse_quota_override_string(header_quota))

    updated_at = settings.updated_at if settings else None
    updated_by = settings.updated_by if settings else None
    change_note = settings.change_note if settings else None

    return PlanContext(
        tier=tier,
        expires_at=expires_at,
        entitlements=frozenset(entitlements),
        quota=quota,
        updated_at=updated_at,
        updated_by=updated_by,
        change_note=change_note,
        checkout_requested=settings.checkout_requested if settings else False,
    )


def resolve_plan_context(request: Request) -> PlanContext:
    """Infer the current plan tier and entitlements for the request."""
    return _build_plan_context(
        header_tier=request.headers.get("x-plan-tier"),
        header_entitlements=request.headers.get("x-plan-entitlements"),
        header_expires_at=request.headers.get("x-plan-expires-at"),
        header_quota=request.headers.get("x-plan-quota"),
    )


def update_plan_context(
    *,
    plan_tier: str,
    entitlements: Sequence[str],
    quota: Mapping[str, Any],
    expires_at: Optional[str],
    updated_by: Optional[str] = None,
    change_note: Optional[str] = None,
    trigger_checkout: bool = False,
    force_checkout_requested: Optional[bool] = None,
) -> PlanContext:
    tier = _normalize_plan_tier(plan_tier)

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in entitlements:
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        cleaned.append(normalized)
        seen.add(normalized)

    expires_dt: Optional[datetime] = None
    if expires_at:
        expires_dt = _parse_iso_datetime(expires_at)
        if expires_dt is None:
            raise ValueError("만료일 포맷이 올바르지 않습니다. ISO8601 형식으로 입력해주세요.")

    base_quota = PLAN_QUOTA_PRESETS.get(tier, PLAN_QUOTA_PRESETS["free"])
    try:
        effective_quota = _apply_quota_overrides(base_quota, quota, strict=True)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    existing_settings = _load_plan_settings()
    checkout_requested = existing_settings.checkout_requested if existing_settings else False
    if force_checkout_requested is not None:
        checkout_requested = force_checkout_requested
    elif trigger_checkout:
        checkout_requested = True

    settings = PersistedPlanSettings(
        plan_tier=tier,
        entitlements=tuple(cleaned),
        quota=effective_quota,
        expires_at=expires_dt,
        updated_at=datetime.now(timezone.utc),
        updated_by=_normalize_actor(updated_by),
        change_note=_normalize_note(change_note),
        checkout_requested=checkout_requested,
    )

    try:
        _store_plan_settings(settings)
    except OSError as exc:
        raise RuntimeError("플랜 설정을 저장하지 못했습니다.") from exc

    if trigger_checkout:
        logger.info(
            "Toss Payments checkout trigger requested for tier=%s by %s.",
            tier,
            settings.updated_by or "unknown",
        )

    append_audit_log(
        filename="plan_audit.jsonl",
        actor=settings.updated_by or "unknown-admin",
        action="plan_update",
        payload={
            "planTier": settings.plan_tier,
            "entitlements": list(settings.entitlements),
            "quota": settings.quota.to_dict(),
            "expiresAt": settings.expires_at.isoformat() if settings.expires_at else None,
            "changeNote": settings.change_note,
            "triggerCheckout": trigger_checkout,
            "forceCheckoutRequested": force_checkout_requested,
            "checkoutRequested": settings.checkout_requested,
        },
    )

    _load_plan_settings(reload=True)
    return _build_plan_context()


def apply_checkout_upgrade(
    *,
    target_tier: PlanTier,
    updated_by: Optional[str],
    change_note: Optional[str] = None,
) -> PlanContext:
    """Upgrade the persisted plan defaults after a successful checkout."""
    existing = _load_plan_settings()
    base_entitlements = set(PLAN_BASE_ENTITLEMENTS.get(target_tier, PLAN_BASE_ENTITLEMENTS["free"]))
    if existing and existing.entitlements:
        base_entitlements.update(existing.entitlements)
    entitlements = sorted(base_entitlements)

    if existing and existing.plan_tier == target_tier:
        quota_payload = existing.quota.to_dict()
    else:
        quota_payload = PLAN_QUOTA_PRESETS.get(target_tier, PLAN_QUOTA_PRESETS["free"]).to_dict()

    expires_str = existing.expires_at.isoformat() if existing and existing.expires_at else None

    return update_plan_context(
        plan_tier=target_tier,
        entitlements=entitlements,
        quota=quota_payload,
        expires_at=expires_str,
        updated_by=updated_by,
        change_note=change_note,
        trigger_checkout=False,
        force_checkout_requested=False,
    )


def clear_checkout_requested(*, updated_by: Optional[str], change_note: Optional[str] = None) -> PlanContext:
    """Clear a pending checkout flag without modifying the active plan tier."""
    existing = _load_plan_settings()
    if not existing:
        return _build_plan_context()

    expires_str = existing.expires_at.isoformat() if existing.expires_at else None

    return update_plan_context(
        plan_tier=existing.plan_tier,
        entitlements=list(existing.entitlements),
        quota=existing.quota.to_dict(),
        expires_at=expires_str,
        updated_by=updated_by or existing.updated_by,
        change_note=change_note,
        trigger_checkout=False,
        force_checkout_requested=False,
    )
