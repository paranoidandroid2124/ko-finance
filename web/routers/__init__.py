from importlib import import_module
from typing import Optional

from . import chat, company, dashboard, news, rag, sectors  # noqa: F401

_filing_module: Optional[object] = None
try:  # pragma: no cover - optional dependency guard
    _filing_module = import_module(".filing", __name__)
except RuntimeError as exc:  # missing optional deps (e.g., python-multipart)
    import warnings

    warnings.warn(f"Filing router disabled: {exc}")
except ModuleNotFoundError:
    _filing_module = None

filing = _filing_module  # expose for FastAPI router registration

__all__ = ["chat", "company", "dashboard", "news", "rag", "sectors"]
if filing is not None:
    __all__.append("filing")
