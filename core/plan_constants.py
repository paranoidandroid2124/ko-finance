"""Shared plan tier constants used across services and routers."""

from __future__ import annotations

from enum import Enum
from typing import Sequence


class PlanTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.value


SUPPORTED_PLAN_TIERS: Sequence[PlanTier] = tuple(PlanTier)

__all__ = ["PlanTier", "SUPPORTED_PLAN_TIERS"]
