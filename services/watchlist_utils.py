"""Shared helpers for watchlist rule classification."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from models.alert import AlertRule


def is_watchlist_rule(rule: AlertRule) -> bool:
    """Heuristically determine whether the alert rule targets a watchlist."""

    name = str(getattr(rule, "name", "") or "").lower()
    if "watch" in name:
        return True

    extras = getattr(rule, "extras", None)
    if isinstance(extras, Mapping):
        category = str(extras.get("category") or "").lower()
        if "watch" in category:
            return True
        tags = extras.get("tags") or extras.get("labels") or []
        if isinstance(tags, (list, tuple, set)):
            for tag in tags:
                if "watch" in str(tag).lower():
                    return True

    condition: Mapping[str, Any] = {}
    raw_condition = getattr(rule, "trigger", None)
    if isinstance(raw_condition, Mapping):
        condition = raw_condition

    scope = str(condition.get("scope") or "").lower()
    if scope == "watchlist":
        return True

    categories = condition.get("categories") or []
    if isinstance(categories, (list, tuple, set)):
        for category in categories:
            if "watch" in str(category).lower():
                return True

    rule_tags = condition.get("tags") or condition.get("labels") or []
    if isinstance(rule_tags, (list, tuple, set)):
        for tag in rule_tags:
            if "watch" in str(tag).lower():
                return True

    return False


__all__ = ["is_watchlist_rule"]
