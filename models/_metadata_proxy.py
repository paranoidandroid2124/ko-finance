"""Helper descriptor to expose JSONB metadata columns without clashing with SQLAlchemy Base."""

from __future__ import annotations

from typing import Any

from database import Base


class JSONMetadataProxy:
    """Descriptor that routes class metadata access to Base.metadata and instance access to a JSON column."""

    def __init__(self, backing_attr: str) -> None:
        self._backing_attr = backing_attr

    def __set_name__(self, owner, name) -> None:  # pragma: no cover - descriptor hook (no logic needed)
        self._name = name

    def __get__(self, instance, owner):
        if instance is None:
            return Base.metadata
        return getattr(instance, self._backing_attr)

    def __set__(self, instance, value: Any) -> None:
        setattr(instance, self._backing_attr, value)


__all__ = ["JSONMetadataProxy"]
