from . import chat, dashboard, news, rag  # noqa: F401

filing = None
try:  # pragma: no cover - optional dependency guard
    from . import filing as _filing  # type: ignore  # noqa: F401

    filing = _filing
except RuntimeError as exc:  # missing optional deps (e.g., python-multipart)
    import warnings

    warnings.warn(f"Filing router disabled: {exc}")
except ModuleNotFoundError:
    filing = None

__all__ = ["chat", "dashboard", "news", "rag"]
if filing is not None:
    __all__.append("filing")
