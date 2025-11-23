"""Plan tier inference helpers, persistence, and feature mapping."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Optional, Sequence

from filelock import FileLock, Timeout

from core.env import env_int, env_str
from core.plan_constants import PlanTier, SUPPORTED_PLAN_TIERS
from services import plan_config_store

logger = logging.getLogger(__name__)


class PlanSettingsConflictError(ValueError):
    """Raised when plan settings have changed since the caller last fetched them."""

    def __init__(self, message: str = "다른 사용자가 플랜 설정을 먼저 저장했습니다. 새로고침 후 다시 시도해주세요.") -> None:
        super().__init__(message)


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


@dataclass(slots=True)
class PlanMemoryFlags:
    """Fine-grained LightMem feature toggles stored with the plan."""

    chat_enabled: bool = False

    def to_dict(self) -> Dict[str, bool]:
        return {
            "chat": self.chat_enabled,
        }


@dataclass(slots=True)
class PlanTrialState:
    """Representation of the optional trial period."""

    tier: PlanTier = PlanTier.PRO
    duration_days: int = 7
    started_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None
    used: bool = False

    def is_active(self, *, at: Optional[datetime] = None) -> bool:
        if not self.started_at or not self.ends_at:
            return False
        reference = at or datetime.now(timezone.utc)
        return self.started_at <= reference < self.ends_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tier": self.tier,
            "durationDays": self.duration_days,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "endsAt": self.ends_at.isoformat() if self.ends_at else None,
            "used": self.used,
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
    memory_flags: PlanMemoryFlags = field(default_factory=PlanMemoryFlags)
    trial_state: PlanTrialState = field(default_factory=PlanTrialState)


@dataclass(slots=True)
class PlanContext:
    """Resolved plan metadata stored on the request."""

    tier: PlanTier
    base_tier: PlanTier
    expires_at: Optional[datetime]
    entitlements: frozenset[str]
    quota: PlanQuota
    updated_at: Optional[datetime] = None
    updated_by: Optional[str] = None
    change_note: Optional[str] = None
    checkout_requested: bool = False
    memory_chat_enabled: bool = False
    trial_tier: Optional[PlanTier] = None
    trial_starts_at: Optional[datetime] = None
    trial_ends_at: Optional[datetime] = None
    trial_duration_days: Optional[int] = None
    trial_active: bool = False
    trial_used: bool = False

    def allows(self, entitlement: str) -> bool:
        return entitlement in self.entitlements

    def feature_flags(self) -> Mapping[str, bool]:
        """Expose consolidated feature flags derived from entitlements."""
        return {
            "search.compare": self.allows("search.compare"),
            "search.export": self.allows("search.export"),
            "evidence.inline_pdf": self.allows("evidence.inline_pdf"),
            "evidence.diff": self.allows("evidence.diff"),
            "rag.core": self.allows("rag.core"),
            "timeline.full": self.allows("timeline.full"),
            "reports.event_export": self.allows("reports.event_export"),
        }

    def memory_flags(self) -> Mapping[str, bool]:
        return {
            "chat": self.memory_chat_enabled,
        }

    def trial_payload(self) -> Optional[Mapping[str, Any]]:
        if not (self.trial_tier or self.trial_active or self.trial_used):
            return None
        return {
            "tier": self.trial_tier or PlanTier.PRO,
            "startsAt": self.trial_starts_at.isoformat() if self.trial_starts_at else None,
            "endsAt": self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            "durationDays": self.trial_duration_days,
            "active": self.trial_active,
            "used": self.trial_used,
        }


_DEFAULT_PLAN_SETTINGS_PATH = Path("uploads") / "admin" / "plan_settings.json"
_PLAN_SETTINGS_CACHE: Optional[PersistedPlanSettings] = None
_PLAN_SETTINGS_CACHE_PATH: Optional[Path] = None
_PLAN_SETTINGS_LOCK_TIMEOUT = env_int("PLAN_SETTINGS_LOCK_TIMEOUT_SECONDS", 5, minimum=1)


@lru_cache(maxsize=None)
def _base_entitlements_for_tier(tier: PlanTier) -> frozenset[str]:
    config = plan_config_store.get_tier_config(tier)
    entries = config.get("entitlements") or []
    cleaned = [str(entry).strip() for entry in entries if str(entry).strip()]
    return frozenset(cleaned)


@lru_cache(maxsize=None)
def _base_quota_for_tier(tier: PlanTier) -> PlanQuota:
    config = plan_config_store.get_tier_config(tier)
    payload = config.get("quota") or {}
    return PlanQuota(
        chat_requests_per_day=payload.get("chatRequestsPerDay"),
        rag_top_k=payload.get("ragTopK"),
        self_check_enabled=bool(payload.get("selfCheckEnabled", False)),
        peer_export_row_limit=payload.get("peerExportRowLimit"),
    )


def _normalize_plan_tier(value: Optional[str | PlanTier]) -> PlanTier:
    if not value:
        return PlanTier.FREE
    lowered = str(value).strip().lower()
    if lowered in SUPPORTED_PLAN_TIERS:
        return PlanTier(lowered)
    return PlanTier.FREE


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


def _parse_memory_flags(payload: Optional[Mapping[str, Any]]) -> PlanMemoryFlags:
    if not isinstance(payload, Mapping):
        return PlanMemoryFlags()
    return PlanMemoryFlags(
        chat_enabled=bool(payload.get("chat")),
    )


def _parse_trial_state(payload: Optional[Mapping[str, Any]]) -> PlanTrialState:
    if not isinstance(payload, Mapping):
        return PlanTrialState()
    tier = _normalize_plan_tier(payload.get("tier"))
    duration = payload.get("durationDays")
    try:
        duration_days = int(duration) if duration is not None else 7
        if duration_days <= 0:
            duration_days = 7
    except (TypeError, ValueError):
        duration_days = 7
    started_at = _parse_iso_datetime(payload.get("startedAt"))
    ends_at = _parse_iso_datetime(payload.get("endsAt"))
    return PlanTrialState(
        tier=tier,
        duration_days=duration_days,
        started_at=started_at,
        ends_at=ends_at,
        used=bool(payload.get("used")),
    )


def _feature_flags_from_entitlements(entitlements: Iterable[str]) -> Dict[str, bool]:
    ent_set = {item.strip() for item in entitlements if item.strip()}
    return {
        "search.compare": "search.compare" in ent_set,
        "search.export": "search.export" in ent_set,
        "evidence.inline_pdf": "evidence.inline_pdf" in ent_set,
        "evidence.diff": "evidence.diff" in ent_set,
        "rag.core": "rag.core" in ent_set,
        "timeline.full": "timeline.full" in ent_set,
        "reports.event_export": "reports.event_export" in ent_set,
    }


def _plan_settings_path() -> Path:
    global _PLAN_SETTINGS_CACHE, _PLAN_SETTINGS_CACHE_PATH
    env_file = env_str("PLAN_SETTINGS_FILE")
    path = Path(env_file) if env_file else _DEFAULT_PLAN_SETTINGS_PATH
    if _PLAN_SETTINGS_CACHE_PATH is not None and _PLAN_SETTINGS_CACHE_PATH != path:
        _PLAN_SETTINGS_CACHE = None
    _PLAN_SETTINGS_CACHE_PATH = path
    return path


def _plan_settings_lock(path: Path) -> FileLock:
    lock_path = path.parent / f"{path.name}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(str(lock_path), timeout=_PLAN_SETTINGS_LOCK_TIMEOUT)


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
    path = _plan_settings_path()
    if _PLAN_SETTINGS_CACHE is not None and not reload:
        return _PLAN_SETTINGS_CACHE

    lock = _plan_settings_lock(path)
    try:
        with lock:
            if not path.exists():
                _PLAN_SETTINGS_CACHE = None
                return None

            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to load plan settings from %s: %s", path, exc)
                _PLAN_SETTINGS_CACHE = None
                return None
    except Timeout as exc:  # pragma: no cover - file lock contention
        logger.error("Plan settings lock timeout at %s: %s", path, exc)
        raise RuntimeError("plan settings are currently locked; please retry.") from exc

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
    base_quota = _base_quota_for_tier(tier)
    quota = _apply_quota_overrides(base_quota, quota_payload, strict=False)

    memory_flags = _parse_memory_flags(payload.get("memoryFlags"))
    trial_state = _parse_trial_state(payload.get("trial"))

    settings = PersistedPlanSettings(
        plan_tier=tier,
        entitlements=tuple(entitlements),
        quota=quota,
        expires_at=_parse_iso_datetime(payload.get("expiresAt")),
        updated_at=_parse_iso_datetime(payload.get("updatedAt")) or datetime.now(timezone.utc),
        updated_by=_normalize_actor(payload.get("updatedBy")),
        change_note=_normalize_note(payload.get("changeNote")),
        checkout_requested=payload.get("checkoutRequested") is True,
        memory_flags=memory_flags,
        trial_state=trial_state,
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
        "memoryFlags": settings.memory_flags.to_dict(),
        "trial": settings.trial_state.to_dict(),
    }
    lock = _plan_settings_lock(path)
    try:
        with lock:
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
    except Timeout as exc:  # pragma: no cover - file lock contention
        logger.error("Failed to acquire lock for plan settings at %s: %s", path, exc)
        raise RuntimeError("plan settings are currently locked; please retry.") from exc
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
    base_tier = _normalize_plan_tier(header_tier or fallback_tier)

    trial_state = settings.trial_state if settings else PlanTrialState()
    trial_active = False
    effective_tier = base_tier
    if not has_header_override and trial_state.is_active():
        effective_tier = trial_state.tier
        trial_active = True

    env_entitlements = _parse_entitlements(env_str("DEFAULT_PLAN_ENTITLEMENTS", ""))
    header_entitlement_set = _parse_entitlements(header_entitlements)

    if settings and not has_header_override and settings.entitlements and not trial_active:
        entitlements = set(settings.entitlements)
    else:
        entitlements = set(_base_entitlements_for_tier(effective_tier))
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

    quota = _base_quota_for_tier(effective_tier)
    if settings and not has_header_override:
        quota = _apply_quota_overrides(quota, settings.quota.to_dict())

    if header_quota:
        quota = _apply_quota_overrides(quota, _parse_quota_override_string(header_quota))

    updated_at = settings.updated_at if settings else None
    updated_by = settings.updated_by if settings else None
    change_note = settings.change_note if settings else None

    memory_flags = settings.memory_flags if settings else PlanMemoryFlags()

    return PlanContext(
        tier=effective_tier,
        base_tier=base_tier,
        expires_at=expires_at,
        entitlements=frozenset(entitlements),
        quota=quota,
        updated_at=updated_at,
        updated_by=updated_by,
        change_note=change_note,
        checkout_requested=settings.checkout_requested if settings else False,
        memory_chat_enabled=memory_flags.chat_enabled,
        trial_tier=trial_state.tier,
        trial_starts_at=trial_state.started_at,
        trial_ends_at=trial_state.ends_at,
        trial_duration_days=trial_state.duration_days,
        trial_active=trial_active,
        trial_used=trial_state.used,
    )


def resolve_plan_context(headers: Optional[Mapping[str, str]] = None) -> PlanContext:
    """Infer the current plan tier and entitlements from an optional header mapping."""
    headers = headers or {}
    return _build_plan_context(
        header_tier=headers.get("x-plan-tier"),
        header_entitlements=headers.get("x-plan-entitlements"),
        header_expires_at=headers.get("x-plan-expires-at"),
        header_quota=headers.get("x-plan-quota"),
    )


def get_active_plan_context() -> PlanContext:
    """Return the persisted plan context for background workers."""
    return _build_plan_context()


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
    memory_flags: Optional[Mapping[str, Any]] = None,
    expected_updated_at: Optional[str] = None,
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

    base_quota = _base_quota_for_tier(tier)
    try:
        effective_quota = _apply_quota_overrides(base_quota, quota, strict=True)
    except ValueError as exc:
        raise ValueError(str(exc)) from exc

    existing_settings = _load_plan_settings()
    if expected_updated_at is not None:
        current_updated_at = (
            existing_settings.updated_at.isoformat()
            if existing_settings and existing_settings.updated_at
            else None
        )
        if current_updated_at != expected_updated_at:
            raise PlanSettingsConflictError()
    checkout_requested = existing_settings.checkout_requested if existing_settings else False
    if force_checkout_requested is not None:
        checkout_requested = force_checkout_requested
    elif trigger_checkout:
        checkout_requested = True

    memory_settings = _parse_memory_flags(memory_flags)
    trial_state = existing_settings.trial_state if existing_settings else PlanTrialState()

    settings = PersistedPlanSettings(
        plan_tier=tier,
        entitlements=tuple(cleaned),
        quota=effective_quota,
        expires_at=expires_dt,
        updated_at=datetime.now(timezone.utc),
        updated_by=_normalize_actor(updated_by),
        change_note=_normalize_note(change_note),
        checkout_requested=checkout_requested,
        memory_flags=memory_settings,
        trial_state=trial_state,
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

    _load_plan_settings(reload=True)
    return _build_plan_context()


def list_plan_presets() -> Sequence[Mapping[str, Any]]:
    """Return canonical plan presets (entitlements, feature flags, quotas) for each tier."""

    presets: list[Mapping[str, Any]] = []
    tier_configs = plan_config_store.list_tier_configs()
    for tier in SUPPORTED_PLAN_TIERS:
        config = tier_configs.get(tier) or plan_config_store.get_tier_config(tier)
        entitlements = sorted(config.get("entitlements") or [])
        quota_payload = config.get("quota") or {}
        presets.append(
            {
                "tier": tier,
                "entitlements": entitlements,
                "feature_flags": _feature_flags_from_entitlements(entitlements),
                "quota": {
                    "chatRequestsPerDay": quota_payload.get("chatRequestsPerDay"),
                    "ragTopK": quota_payload.get("ragTopK"),
                    "selfCheckEnabled": bool(quota_payload.get("selfCheckEnabled", False)),
                    "peerExportRowLimit": quota_payload.get("peerExportRowLimit"),
                },
            }
        )
    return presets


def start_plan_trial(
    *,
    updated_by: Optional[str],
    target_tier: PlanTier = PlanTier.PRO,
    duration_days: Optional[int] = None,
) -> PlanContext:
    """Activate the Pro trial window if it's available."""

    settings = _load_plan_settings()
    actor = _normalize_actor(updated_by)
    if not settings:
        # bootstrap plan settings from the current resolved context so that trial activation works on first run
        current = _build_plan_context()
        settings = PersistedPlanSettings(
            plan_tier=_normalize_plan_tier(current.base_tier),
            entitlements=tuple(sorted(current.entitlements)),
            quota=PlanQuota(
                chat_requests_per_day=current.quota.chat_requests_per_day,
                rag_top_k=current.quota.rag_top_k,
                self_check_enabled=current.quota.self_check_enabled,
                peer_export_row_limit=current.quota.peer_export_row_limit,
            ),
            expires_at=current.expires_at,
            updated_at=datetime.now(timezone.utc),
            updated_by=actor or "trial-bootstrap",
            change_note="trial_bootstrap",
            checkout_requested=False,
            memory_flags=PlanMemoryFlags(chat_enabled=current.memory_chat_enabled),
            trial_state=PlanTrialState(),
        )
        _store_plan_settings(settings)

    trial = settings.trial_state or PlanTrialState()
    if trial.is_active():
        raise ValueError("Trial is already active.")
    if trial.used:
        raise ValueError("Trial has already been used.")

    now = datetime.now(timezone.utc)
    duration = duration_days if duration_days and duration_days > 0 else trial.duration_days or 7

    settings.trial_state = PlanTrialState(
        tier=target_tier,
        duration_days=duration,
        started_at=now,
        ends_at=now + timedelta(days=duration),
        used=True,
    )
    settings.updated_at = now
    settings.updated_by = actor
    settings.change_note = "trial_started"

    _store_plan_settings(settings)

    return _build_plan_context()


def apply_checkout_upgrade(
    *,
    target_tier: PlanTier,
    updated_by: Optional[str],
    change_note: Optional[str] = None,
) -> PlanContext:
    """Upgrade the persisted plan defaults after a successful checkout."""
    existing = _load_plan_settings()
    base_entitlements = set(_base_entitlements_for_tier(target_tier))
    if existing and existing.entitlements:
        base_entitlements.update(existing.entitlements)
    entitlements = sorted(base_entitlements)

    if existing and existing.plan_tier == target_tier:
        quota_payload = existing.quota.to_dict()
    else:
        quota_payload = _base_quota_for_tier(target_tier).to_dict()

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
        memory_flags=existing.memory_flags.to_dict() if existing else None,
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
        memory_flags=existing.memory_flags.to_dict(),
    )
