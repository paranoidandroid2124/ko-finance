"""Nuvien Focus Score: Compute a 4-lens event quality score (Impact, Clarity, Consistency, Confirmation).

This module is self-contained and uses only in-memory inputs. Integration points:
 - Pass event-level metrics (CAAR, p_value, derived fields) and distributions from your data layer.
 - Use the returned scores to render UI cards or filter/sort events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Set, Tuple


def clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def percentile_rank(value: float, population: Sequence[float]) -> Optional[float]:
    """Return percentile rank (0~100) of value within population. None if population empty or value None."""
    if value is None:
        return None
    values = [v for v in population if v is not None]
    if not values:
        return None
    values = sorted(values)
    count = sum(1 for v in values if v <= value)
    return (count / len(values)) * 100.0


@dataclass
class NewsArticle:
    reliability: Optional[str] = None  # "high" | "medium" | "low" | None
    publisher: Optional[str] = None


@dataclass
class FocusScoreContext:
    # Impact
    caar_distribution: Sequence[float] = ()
    # Consistency
    stddev_distribution: Sequence[float] = ()
    restatement_count_1y: int = 0
    # Clarity
    required_fields: Sequence[str] = ()
    present_fields: Set[str] = frozenset()
    is_delayed: bool = False
    summary_chars: int = 0
    min_summary_chars: int = 300
    # Confirmation
    articles: Sequence[NewsArticle] = ()


@dataclass
class FocusScoreInput:
    event_type: str
    cap_bucket: str = "ALL"
    caar: Optional[float] = None
    p_value: Optional[float] = None
    # Consistency
    past_caar_stddev: Optional[float] = None


def _calculate_impact(event: FocusScoreInput, ctx: FocusScoreContext) -> float:
    raw = percentile_rank(abs(event.caar), ctx.caar_distribution) if event.caar is not None else None
    raw_score = raw if raw is not None else 0.0

    adjustment = 0.0
    if event.p_value is not None:
        if event.p_value < 0.05:
            adjustment = 10.0
        elif event.p_value > 0.1:
            adjustment = -15.0

    return clamp(raw_score + adjustment)


def _calculate_clarity(ctx: FocusScoreContext) -> float:
    score = 100.0

    missing = set(ctx.required_fields) - set(ctx.present_fields or [])
    score -= 15.0 * len(missing)

    if ctx.summary_chars < ctx.min_summary_chars:
        score -= 10.0

    if ctx.is_delayed:
        score -= 20.0

    return clamp(score)


def _calculate_consistency(event: FocusScoreInput, ctx: FocusScoreContext) -> float:
    deviation_penalty = 0.0
    rank = percentile_rank(event.past_caar_stddev, ctx.stddev_distribution) if event.past_caar_stddev is not None else None
    if rank is not None:
        deviation_penalty = rank

    restatement_penalty = min(20.0, max(0, ctx.restatement_count_1y) * 5.0)
    score = 100.0 - deviation_penalty - restatement_penalty
    return clamp(score)


def _calculate_confirmation(ctx: FocusScoreContext) -> float:
    if not ctx.articles:
        return 0.0

    count = len(ctx.articles)
    high_reliability = sum(1 for a in ctx.articles if (a.reliability or "").lower() == "high")
    unique_publishers = {a.publisher for a in ctx.articles if a.publisher}

    volume_bonus = min(50.0, count * 10.0)
    reliability_bonus = high_reliability * 10.0
    diversity_bonus = len(unique_publishers) * 5.0

    return clamp(volume_bonus + reliability_bonus + diversity_bonus)


def calculate_focus_score(event: FocusScoreInput, ctx: FocusScoreContext) -> dict:
    impact = _calculate_impact(event, ctx)
    clarity = _calculate_clarity(ctx)
    consistency = _calculate_consistency(event, ctx)
    confirmation = _calculate_confirmation(ctx)

    weights = {"impact": 0.35, "clarity": 0.20, "consistency": 0.25, "confirmation": 0.20}
    final_score = (
        impact * weights["impact"]
        + clarity * weights["clarity"]
        + consistency * weights["consistency"]
        + confirmation * weights["confirmation"]
    )

    return {
        "total_score": round(final_score),
        "sub_scores": {
          "impact": round(impact, 1),
          "clarity": round(clarity, 1),
          "consistency": round(consistency, 1),
          "confirmation": round(confirmation, 1),
        },
    }


__all__ = [
    "FocusScoreContext",
    "FocusScoreInput",
    "NewsArticle",
    "calculate_focus_score",
]
