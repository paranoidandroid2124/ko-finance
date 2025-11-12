from importlib import import_module
from typing import Optional

from . import (  # noqa: F401
    admin,
    admin_llm,
    admin_ops,
    admin_rag,
    admin_ui,
    auth,
    alerts,
    chat,
    campaign,
    analytics,
    company,
    dashboard,
    event_study,
    health,
    public,
    reports,
    news,
    payments,
    plan,
    orgs,
    rag,
    ops,
    search,
    sectors,
    user_settings,
)

_filing_module: Optional[object] = None
try:  # pragma: no cover - optional dependency guard
    _filing_module = import_module(".filing", __name__)
except RuntimeError as exc:  # missing optional deps (e.g., python-multipart)
    import warnings

    warnings.warn(f"Filing router disabled: {exc}")
except ModuleNotFoundError:
    _filing_module = None

filing = _filing_module  # expose for FastAPI router registration

__all__ = [
    "admin",
    "admin_llm",
    "admin_ops",
    "admin_rag",
    "admin_ui",
    "auth",
    "alerts",
    "chat",
    "campaign",
    "analytics",
    "company",
    "dashboard",
    "event_study",
    "health",
    "public",
    "news",
    "payments",
    "plan",
    "orgs",
    "reports",
    "rag",
    "ops",
    "search",
    "sectors",
    "user_settings",
]
if filing is not None:
    __all__.append("filing")
