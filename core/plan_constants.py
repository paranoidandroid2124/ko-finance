"""Shared plan tier constants used across services and routers."""

from __future__ import annotations

from typing import Literal, Sequence

PlanTier = Literal["free", "starter", "pro", "enterprise"]

SUPPORTED_PLAN_TIERS: Sequence[str] = ("free", "starter", "pro", "enterprise")

__all__ = ["PlanTier", "SUPPORTED_PLAN_TIERS"]
