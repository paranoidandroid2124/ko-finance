"""Lazy-loading package exports for FastAPI routers."""

from __future__ import annotations

import warnings
from importlib import import_module
from typing import Dict, Optional

_ROUTER_MODULES = [
    "admin",
    "admin_llm",
    "admin_ops",
    "admin_rag",
    "admin_ui",
    "auth",
    "alerts",
    "boards",
    "chat",
    "campaign",
    "analytics",
    "company",
    "dashboard",
    "event_study",
    "health",
    "public",
    "reports",
    "news",
    "onboarding",
    "payments",
    "plan",
    "orgs",
    "table_explorer",
    "notebooks",
    "rag",
    "ops",
    "search",
    "sectors",
    "scim",
    "user_settings",
    "workspaces",
]

__all__ = list(_ROUTER_MODULES)

_lazy_cache: Dict[str, object] = {}


def __getattr__(name: str) -> object:
    if name in _lazy_cache:
        return _lazy_cache[name]
    if name in _ROUTER_MODULES:
        module = import_module(f".{name}", __name__)
        _lazy_cache[name] = module
        return module
    if name == "filing":
        module = _load_optional_filing_router()
        if module is None:
            raise AttributeError(name)
        _lazy_cache[name] = module
        return module
    raise AttributeError(name)


_filing_module: Optional[object] = None


def _load_optional_filing_router() -> Optional[object]:
    global _filing_module
    if _filing_module is not None:
        return _filing_module
    try:  # pragma: no cover - optional dependency guard
        _filing_module = import_module(".filing", __name__)
        if "filing" not in __all__:
            __all__.append("filing")
    except RuntimeError as exc:  # missing optional deps (e.g., python-multipart)
        warnings.warn(f"Filing router disabled: {exc}")
        _filing_module = None
    except ModuleNotFoundError:
        _filing_module = None
    return _filing_module
