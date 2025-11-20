"""Configuration helpers for the LightMem-inspired memory pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.env import env_bool, env_int


@dataclass(frozen=True)
class MemoryFeatureFlags:
    """Feature gates controlling whether memory subsystems should be used."""

    default_enabled: bool
    watchlist_enabled: bool

    @classmethod
    def load(cls) -> "MemoryFeatureFlags":
        return cls(
            default_enabled=env_bool("LIGHTMEM_ENABLED", False),
            watchlist_enabled=env_bool("LIGHTMEM_WATCHLIST_ENABLED", False),
        )


@dataclass(frozen=True)
class MemoryRuntimeSettings:
    """Runtime tuning knobs for TTLs, retrieval counts, etc."""

    session_ttl_minutes: int
    retrieval_k: int
    max_prompt_chars: int

    @classmethod
    def load(cls) -> "MemoryRuntimeSettings":
        return cls(
            session_ttl_minutes=env_int("LIGHTMEM_SESSION_TTL_MINUTES", 120, minimum=10),
            retrieval_k=env_int("LIGHTMEM_RETRIEVAL_K", 5, minimum=1),
            max_prompt_chars=env_int("LIGHTMEM_SENSORY_MAX_CHARS", 1500, minimum=200),
        )
