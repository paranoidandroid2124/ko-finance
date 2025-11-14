"""Shared helpers for summarising watchlist alert payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple
from uuid import UUID

from core.logging import get_logger
from services import watchlist_service

logger = get_logger(__name__)


@dataclass(slots=True)
class WatchlistRuleSummary:
    rule_id: str
    name: str
    event_count: int = 0
    tickers: set[str] = field(default_factory=set)
    channels: set[str] = field(default_factory=set)
    last_triggered_at: Optional[datetime] = None
    last_headline: Optional[str] = None
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ruleId": self.rule_id,
            "name": self.name,
            "eventCount": self.event_count,
            "tickers": sorted(self.tickers),
            "channels": sorted(self.channels),
            "lastTriggeredAt": self.last_triggered_at.isoformat() if self.last_triggered_at else None,
            "lastHeadline": self.last_headline,
            "description": self.description,
        }


def owner_filters(user_id: Optional[UUID], org_id: Optional[UUID]) -> Dict[str, Optional[Any]]:
    filters: Dict[str, Optional[Any]] = {}
    if user_id:
        filters["user_id"] = user_id
    if org_id:
        filters["org_id"] = org_id
    return filters


def collect_watchlist_items(
    db,
    *,
    user_id: Optional[UUID],
    org_id: Optional[UUID],
    limit: int = 200,
    window_minutes: int = 1440,
) -> Tuple[Sequence[Mapping[str, Any]], Mapping[str, Any]]:
    if user_id is None and org_id is None:
        return [], {}
    try:
        payload = watchlist_service.collect_watchlist_alerts(
            db,
            window_minutes=window_minutes,
            limit=limit,
            owner_filters=owner_filters(user_id, org_id),
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to collect watchlist alerts: %s", exc)
        return [], {}
    items = payload.get("items")
    summary = payload.get("summary") or {}
    if not isinstance(items, Sequence):
        return [], summary
    return items, summary


def parse_iso_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def summarise_watchlist_rules(items: Sequence[Mapping[str, Any]]) -> list[WatchlistRuleSummary]:
    aggregated: Dict[str, WatchlistRuleSummary] = {}
    for item in items:
        rule_id = str(item.get("ruleId") or "").strip()
        if not rule_id:
            continue
        summary = aggregated.setdefault(
            rule_id,
            WatchlistRuleSummary(
                rule_id=rule_id,
                name=str(item.get("ruleName") or rule_id),
                description=item.get("summary"),
            ),
        )
        summary.event_count += 1
        ticker = str(item.get("ticker") or "").strip().upper()
        if ticker:
            summary.tickers.add(ticker)
        rule_tickers = item.get("ruleTickers") or []
        if isinstance(rule_tickers, Sequence):
            for value in rule_tickers:
                normalized = str(value or "").strip().upper()
                if normalized:
                    summary.tickers.add(normalized)
        channel = str(item.get("channel") or "").strip().lower()
        if channel:
            summary.channels.add(channel)
        delivered_at = parse_iso_timestamp(item.get("deliveredAt") or item.get("eventTime"))
        if delivered_at and (summary.last_triggered_at is None or delivered_at > summary.last_triggered_at):
            summary.last_triggered_at = delivered_at
            summary.last_headline = (
                item.get("headline")
                or item.get("summary")
                or item.get("message")
                or item.get("category")
                or item.get("eventType")
            )
    ordered = sorted(
        aggregated.values(),
        key=lambda entry: (entry.event_count, entry.last_triggered_at or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )
    return ordered


def convert_items_to_alert_payload(items: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    alerts: list[Dict[str, Any]] = []
    for item in items:
        delivery_id = str(item.get("deliveryId") or item.get("ruleId") or "").strip()
        if not delivery_id:
            continue
        delivered_at = parse_iso_timestamp(item.get("deliveredAt"))
        ticker = str(item.get("ticker") or "").strip().upper()
        alerts.append(
            {
                "id": delivery_id,
                "title": str(item.get("headline") or item.get("ruleName") or "Watchlist Alert"),
                "body": (
                    item.get("summary")
                    or f"{ticker or ''} {item.get('category') or ''}".strip()
                    or item.get("message")
                    or "알림 상세를 확인하세요."
                ),
                "ticker": ticker,
                "timestamp": delivered_at,
                "sentiment": item.get("sentiment"),
                "targetUrl": item.get("url"),
            }
        )
    return alerts


def build_quick_link_payload(summary: Mapping[str, Any], items: Sequence[Mapping[str, Any]]) -> list[Dict[str, str]]:
    links: list[Dict[str, str]] = [{"label": "통합 검색 열기", "href": "/search", "type": "search"}]
    tickers: list[str] = []
    summary_tickers = summary.get("topTickers") or []
    if isinstance(summary_tickers, list):
        tickers.extend(str(value).upper() for value in summary_tickers if isinstance(value, str))
    for item in items:
        ticker = str(item.get("ticker") or "").strip().upper()
        if ticker:
            tickers.append(ticker)
    seen: set[str] = set()
    for ticker in tickers:
        if ticker in seen:
            continue
        seen.add(ticker)
        links.append({"label": f"{ticker} 상세 보기", "href": f"/company/{ticker}", "type": "company"})
        if len(links) >= 6:
            break
    return links


def build_board_entries(items: Sequence[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    aggregates: Dict[str, Dict[str, Any]] = {}
    for item in items:
        ticker = str(item.get("ticker") or "").strip().upper()
        if not ticker and item.get("ruleTickers"):
            first = next((value for value in item.get("ruleTickers") if value), "")
            ticker = str(first).strip().upper()
        if not ticker:
            continue
        entry = aggregates.setdefault(
            ticker,
            {
                "ticker": ticker,
                "corpName": item.get("company"),
                "sector": (item.get("category") or "").title(),
                "eventCount": 0,
                "lastHeadline": None,
                "lastEventAt": None,
                "sentiments": [],
                "targetUrl": None,
            },
        )
        entry["eventCount"] += 1
        sentiment = item.get("sentiment")
        if isinstance(sentiment, (int, float)):
            entry["sentiments"].append(float(sentiment))
        delivered_at = parse_iso_timestamp(item.get("deliveredAt") or item.get("eventTime"))
        if delivered_at and (entry["lastEventAt"] is None or delivered_at > entry["lastEventAt"]):
            entry["lastEventAt"] = delivered_at
            entry["lastHeadline"] = item.get("headline") or item.get("summary") or item.get("message")
            entry["corpName"] = item.get("company") or entry["corpName"]
            entry["targetUrl"] = item.get("url")

    entries: list[Dict[str, Any]] = []
    for data in aggregates.values():
        sentiments = data["sentiments"]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else None
        entries.append(
            {
                "ticker": data["ticker"],
                "corpName": data["corpName"],
                "sector": data["sector"],
                "eventCount": data["eventCount"],
                "lastHeadline": data["lastHeadline"],
                "lastEventAt": data["lastEventAt"].isoformat() if data["lastEventAt"] else None,
                "sentiment": avg_sentiment,
                "targetUrl": data["targetUrl"],
            }
        )
    entries.sort(key=lambda entry: entry["eventCount"], reverse=True)
    return entries


def build_board_timeline(items: Sequence[Mapping[str, Any]], *, limit: int = 80) -> list[Dict[str, Any]]:
    timeline: list[Tuple[datetime, Dict[str, Any]]] = []
    for item in items:
        delivered_at = parse_iso_timestamp(item.get("deliveredAt") or item.get("eventTime")) or datetime.now(timezone.utc)
        event = {
            "id": str(item.get("deliveryId") or item.get("ruleId")),
            "headline": item.get("headline") or item.get("summary") or item.get("message") or "Watchlist 알림",
            "summary": item.get("summary") or item.get("category"),
            "channel": item.get("channel"),
            "sentiment": item.get("sentiment") if isinstance(item.get("sentiment"), (int, float)) else None,
            "deliveredAt": delivered_at.isoformat(),
            "url": item.get("url"),
        }
        timeline.append((delivered_at, event))
    timeline.sort(key=lambda entry: entry[0], reverse=True)
    return [event for _, event in timeline[:limit]]


__all__ = [
    "WatchlistRuleSummary",
    "owner_filters",
    "collect_watchlist_items",
    "summarise_watchlist_rules",
    "convert_items_to_alert_payload",
    "build_quick_link_payload",
    "build_board_entries",
    "build_board_timeline",
    "parse_iso_timestamp",
]
