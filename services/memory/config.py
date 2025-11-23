"""Configuration helpers for the LightMem-inspired memory pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.env import env_bool, env_int, env_float


@dataclass(frozen=True)
class MemoryFeatureFlags:
    """Feature gates controlling whether memory subsystems should be used."""

    default_enabled: bool
    user_profile_enabled: bool

    @classmethod
    def load(cls) -> "MemoryFeatureFlags":
        return cls(
            default_enabled=env_bool("LIGHTMEM_ENABLED", False),
            user_profile_enabled=env_bool("LIGHTMEM_PROFILE_ENABLED", True),
        )


@dataclass(frozen=True)
class MemoryRuntimeSettings:
    """Runtime tuning knobs for TTLs, retrieval counts, etc."""

    session_ttl_minutes: int
    profile_ttl_minutes: int
    profile_max_highlights: int
    profile_max_chars: int
    summary_trigger_turns: int
    retrieval_k: int
    min_relevance_score: float
    max_record_age_days: Optional[int]
    max_prompt_chars: int

    @classmethod
    def load(cls) -> "MemoryRuntimeSettings":
        max_age_raw = env_int("LIGHTMEM_MAX_RECORD_AGE_DAYS", 365, minimum=None)
        max_age = max_age_raw if max_age_raw and max_age_raw > 0 else None
        return cls(
            session_ttl_minutes=env_int("LIGHTMEM_SESSION_TTL_MINUTES", 120, minimum=10),
            profile_ttl_minutes=env_int("LIGHTMEM_PROFILE_TTL_MINUTES", 1440, minimum=60),
            profile_max_highlights=env_int("LIGHTMEM_PROFILE_MAX_HIGHLIGHTS", 5, minimum=1),
            profile_max_chars=env_int("LIGHTMEM_PROFILE_MAX_CHARS", 240, minimum=60),
            summary_trigger_turns=env_int("LIGHTMEM_SUMMARY_TRIGGER_TURNS", 10, minimum=3),
            retrieval_k=env_int("LIGHTMEM_RETRIEVAL_K", 5, minimum=1),
            # Lower default to reduce over-filtering; tune via env for stricter runs.
            min_relevance_score=env_float("LIGHTMEM_MIN_SCORE", 0.05, minimum=0.0),
            max_record_age_days=max_age,
            max_prompt_chars=env_int("LIGHTMEM_SENSORY_MAX_CHARS", 1500, minimum=200),
        )
