"""Utility helpers for parsing relative date expressions in user queries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


@dataclass(frozen=True)
class RelativeDateRange:
    label: str
    start: datetime
    end: datetime


def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def _end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=999_999)


def _week_range(local_dt: datetime) -> tuple[datetime, datetime]:
    start = _start_of_day(local_dt - timedelta(days=local_dt.weekday()))
    end = _end_of_day(start + timedelta(days=6))
    return start, end


def _month_start(local_dt: datetime) -> datetime:
    return _start_of_day(local_dt.replace(day=1))


def _add_months(local_dt: datetime, months: int) -> datetime:
    year = local_dt.year + ((local_dt.month - 1 + months) // 12)
    month = ((local_dt.month - 1 + months) % 12) + 1
    return local_dt.replace(year=year, month=month)


def _month_range(local_dt: datetime) -> tuple[datetime, datetime]:
    start = _month_start(local_dt)
    next_month_start = _month_start(_add_months(start, 1))
    end = next_month_start - timedelta(microseconds=1)
    return start, end


RELATIVE_PATTERNS = [
    (
        re.compile(r"(오늘|금일|today)\b", re.IGNORECASE),
        "today",
        lambda now: (_start_of_day(now), _end_of_day(now)),
    ),
    (
        re.compile(r"(어제|전일|yesterday)\b", re.IGNORECASE),
        "yesterday",
        lambda now: (
            _start_of_day(now - timedelta(days=1)),
            _end_of_day(now - timedelta(days=1)),
        ),
    ),
    (
        re.compile(r"(그제|the day before yesterday)\b", re.IGNORECASE),
        "two_days_ago",
        lambda now: (
            _start_of_day(now - timedelta(days=2)),
            _end_of_day(now - timedelta(days=2)),
        ),
    ),
    (
        re.compile(r"(이번\s*주|this week)", re.IGNORECASE),
        "this_week",
        lambda now: _week_range(now),
    ),
    (
        re.compile(r"(지난\s*주|저번\s*주|last week)", re.IGNORECASE),
        "last_week",
        lambda now: _week_range(now - timedelta(days=7)),
    ),
    (
        re.compile(r"(이번\s*달|이번\s*월|this month)", re.IGNORECASE),
        "this_month",
        lambda now: _month_range(now),
    ),
    (
        re.compile(r"(지난\s*달|저번\s*달|last month)", re.IGNORECASE),
        "last_month",
        lambda now: _month_range(_add_months(now, -1)),
    ),
]


def parse_relative_date_range(
    text: str,
    *,
    now: Optional[datetime] = None,
    timezone_hint: ZoneInfo = KST,
) -> Optional[RelativeDateRange]:
    """Parse relative date expressions (예: 오늘, 어제, 지난주) into concrete ranges.

    Returns:
        RelativeDateRange with UTC-aware boundaries, or None if not detected.
    """
    if not text:
        return None

    reference = now or datetime.now(timezone.utc)
    local_now = reference.astimezone(timezone_hint)

    for pattern, label, builder in RELATIVE_PATTERNS:
        if pattern.search(text):
            start_local, end_local = builder(local_now)
            start_utc = start_local.astimezone(timezone.utc)
            end_utc = end_local.astimezone(timezone.utc)
            return RelativeDateRange(label=label, start=start_utc, end=end_utc)

    return None


__all__ = ["RelativeDateRange", "parse_relative_date_range"]
