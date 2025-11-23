"""Persistent storage for base plan tier entitlements and quotas."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from core.logging import get_logger
from datetime import datetime, timezone
from services.json_store import JsonStore

DEFAULT_PLAN_CONFIG_PATH = Path("uploads") / "admin" / "plan_config.json"

logger = get_logger(__name__)
_PLAN_CONFIG_STORE = JsonStore(
    path_env="PLAN_CONFIG_FILE",
    default_path=DEFAULT_PLAN_CONFIG_PATH,
)

_DEFAULT_PLAN_CONFIG: Dict[str, Any] = {
    "tiers": {
        "free": {
            "entitlements": ["rag.core"],
            "quota": {
                "chatRequestsPerDay": 20,
                "ragTopK": 4,
                "selfCheckEnabled": False,
                "peerExportRowLimit": 0,
            },
        },
        "starter": {
            "entitlements": [
                "search.export",
                "rag.core",
                "evidence.inline_pdf",
            ],
            "quota": {
                "chatRequestsPerDay": 80,
                "ragTopK": 5,
                "selfCheckEnabled": True,
                "peerExportRowLimit": 50,
            },
        },
        "pro": {
            "entitlements": [
                "search.compare",
                "search.export",
                "evidence.inline_pdf",
                "rag.core",
                "reports.event_export",
            ],
            "quota": {
                "chatRequestsPerDay": 500,
                "ragTopK": 6,
                "selfCheckEnabled": True,
                "peerExportRowLimit": 100,
            },
        },
        "enterprise": {
            "entitlements": [
                "search.compare",
                "search.export",
                "evidence.inline_pdf",
                "evidence.diff",
                "rag.core",
                "timeline.full",
                "reports.event_export",
            ],
            "quota": {
                "chatRequestsPerDay": None,
                "ragTopK": 10,
                "selfCheckEnabled": True,
                "peerExportRowLimit": None,
            },
        },
    },
    "updated_at": None,
    "updated_by": None,
    "note": None,
}


def _default_config_payload() -> Dict[str, Any]:
    return deepcopy(_DEFAULT_PLAN_CONFIG)


def _normalize_entitlements(values: Optional[Iterable[Any]], fallback: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for item in values or []:
        text = str(item or "").strip()
        if text and text not in seen:
            normalized.append(text)
            seen.add(text)
    if not normalized:
        normalized = [entry for entry in fallback if entry]
    return normalized


def _normalize_quota(payload: Optional[Mapping[str, Any]], fallback: Mapping[str, Any]) -> dict[str, Optional[int] | bool]:
    quota = {
        "chatRequestsPerDay": fallback.get("chatRequestsPerDay"),
        "ragTopK": fallback.get("ragTopK"),
        "selfCheckEnabled": bool(fallback.get("selfCheckEnabled", False)),
        "peerExportRowLimit": fallback.get("peerExportRowLimit"),
    }
    if not isinstance(payload, Mapping):
        return quota

    def _safe_int(key: str, value: Any) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            candidate = int(value)
        except (TypeError, ValueError):
            logger.warning("Invalid %s override in plan config ignored: %s", key, value)
            return quota[key]  # type: ignore[index]
        if candidate < 0:
            logger.warning("Invalid %s (negative) in plan config ignored: %s", key, value)
            return quota[key]  # type: ignore[index]
        return candidate

    if "chatRequestsPerDay" in payload:
        quota["chatRequestsPerDay"] = _safe_int("chatRequestsPerDay", payload.get("chatRequestsPerDay"))
    if "ragTopK" in payload:
        quota["ragTopK"] = _safe_int("ragTopK", payload.get("ragTopK"))
    if "peerExportRowLimit" in payload:
        quota["peerExportRowLimit"] = _safe_int("peerExportRowLimit", payload.get("peerExportRowLimit"))
    if "selfCheckEnabled" in payload:
        value = payload.get("selfCheckEnabled")
        if isinstance(value, bool):
            quota["selfCheckEnabled"] = value
        elif isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "y"}:
                quota["selfCheckEnabled"] = True
            elif normalized in {"0", "false", "no", "n"}:
                quota["selfCheckEnabled"] = False
            else:
                logger.warning("Invalid selfCheckEnabled override in plan config ignored: %s", value)
        else:
            logger.warning("Invalid selfCheckEnabled override in plan config ignored: %s", value)
    return quota


def _base_tier_config(tier: str) -> Dict[str, Any]:
    base = _DEFAULT_PLAN_CONFIG["tiers"].get(tier)
    if base is None:
        base = _DEFAULT_PLAN_CONFIG["tiers"]["free"]
    return {
        "entitlements": list(base.get("entitlements") or []),
        "quota": dict(base.get("quota") or {}),
    }


def _normalize_tier_entry(tier: str, entry: Mapping[str, Any]) -> Dict[str, Any]:
    base = _base_tier_config(tier)
    entitlements = _normalize_entitlements(entry.get("entitlements"), base["entitlements"])
    quota = _normalize_quota(entry.get("quota"), base["quota"])
    return {"entitlements": entitlements, "quota": quota}


def _merge_plan_config(raw: Mapping[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(_DEFAULT_PLAN_CONFIG)
    tiers_raw = raw.get("tiers")

    def _iter_entries(source: Any) -> Iterable[tuple[str, Mapping[str, Any]]]:
        if isinstance(source, Mapping):
            for key, value in source.items():
                if isinstance(value, Mapping):
                    yield str(key), value
        elif isinstance(source, list):
            for item in source:
                if isinstance(item, Mapping):
                    tier = str(item.get("tier") or "").strip()
                    if tier:
                        yield tier, item

    if tiers_raw:
        for tier, entry in _iter_entries(tiers_raw):
            merged["tiers"][tier] = _normalize_tier_entry(tier, entry)

    merged["updated_at"] = raw.get("updated_at")
    merged["updated_by"] = raw.get("updated_by")
    merged["note"] = raw.get("note")
    return merged


def load_plan_config(*, reload: bool = False) -> Dict[str, Any]:
    """Load the persisted plan config with defaults applied."""

    return _PLAN_CONFIG_STORE.load(
        loader=_merge_plan_config,
        fallback=_default_config_payload,
        reload=reload,
    )


def reload_plan_config() -> Dict[str, Any]:
    """Force reload of the plan config (used by tests/admin tools)."""

    return load_plan_config(reload=True)


def clear_plan_config_cache() -> None:
    """Clear the in-memory config cache."""

    _PLAN_CONFIG_STORE.clear_cache()


def get_tier_config(tier: str) -> Dict[str, Any]:
    """Return the merged config block for a tier."""

    config = load_plan_config()
    tiers = config.get("tiers") or {}
    entry = tiers.get(tier)
    if not entry:
        entry = tiers.get("free") or _base_tier_config("free")
    return deepcopy(entry)


def list_tier_configs() -> Dict[str, Dict[str, Any]]:
    """Return all tier configs keyed by tier name."""

    config = load_plan_config()
    tiers = config.get("tiers") or {}
    return {tier: deepcopy(entry) for tier, entry in tiers.items()}


def update_plan_config(
    tiers: Iterable[Mapping[str, Any]],
    *,
    updated_by: Optional[str],
    note: Optional[str],
) -> Dict[str, Any]:
    """Persist overrides for the supplied tiers."""

    normalized_entries: Dict[str, Dict[str, Any]] = {}
    for entry in tiers:
        if not isinstance(entry, Mapping):
            continue
        tier = str(entry.get("tier") or "").strip()
        if not tier:
            continue
        normalized_entries[tier] = _normalize_tier_entry(tier, entry)

    config = load_plan_config()
    for tier, payload in normalized_entries.items():
        config["tiers"][tier] = payload

    config["updated_at"] = datetime.now(timezone.utc).isoformat()
    config["updated_by"] = (updated_by or "").strip() or None
    config["note"] = (note or "").strip() or None

    _PLAN_CONFIG_STORE.save(config)

    return deepcopy(config)


__all__ = [
    "clear_plan_config_cache",
    "get_tier_config",
    "list_tier_configs",
    "load_plan_config",
    "reload_plan_config",
    "update_plan_config",
]
