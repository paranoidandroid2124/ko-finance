"""Singleton accessor for the LightMem memory service."""

from __future__ import annotations

from services.memory.service import MemoryService

MEMORY_SERVICE = MemoryService()

__all__ = ["MEMORY_SERVICE"]
