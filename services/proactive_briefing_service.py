"""Helpers for generating/serving daily proactive (F1) briefings."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.logging import get_logger
from models.company import FilingEvent
from models.filing import Filing
from models.news import NewsSignal
from models.proactive_notification import ProactiveNotification

logger = get_logger(__name__)

PROACTIVE_SOURCE_TYPE = "proactive.insight.daily"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def generate_daily_briefing(
    db: Session,
    *,
    user_id: uuid.UUID,
    today: Optional[date] = None,
    items: Optional[List[Dict[str, str]]] = None,
) -> ProactiveNotification:
    """Upsert a daily proactive insight payload into proactive_notifications."""

    now = _now_utc()
    target_date = today or now.date()
    source_id = target_date.isoformat()
    payload_items = items or []

    existing = (
        db.query(ProactiveNotification)
        .filter(
            ProactiveNotification.user_id == user_id,
            ProactiveNotification.source_type == PROACTIVE_SOURCE_TYPE,
            ProactiveNotification.source_id == source_id,
        )
        .one_or_none()
    )

    meta_payload = {
        "items": payload_items,
        "generated_at": now.isoformat(),
    }

    if existing:
        existing.title = existing.title or "프로액티브 인사이트"
        existing.summary = existing.summary or "오늘의 개인화 인사이트"
        existing.meta = meta_payload
        existing.created_at = existing.created_at or now
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    record = ProactiveNotification(
        user_id=user_id,
        source_type=PROACTIVE_SOURCE_TYPE,
        source_id=source_id,
        title="프로액티브 인사이트",
        summary="오늘의 개인화 인사이트",
        target_url="/dashboard",
        meta=meta_payload,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_latest_briefing(db: Session, *, user_id: uuid.UUID) -> Optional[ProactiveNotification]:
    return (
        db.query(ProactiveNotification)
        .filter(
            ProactiveNotification.user_id == user_id,
            ProactiveNotification.source_type == PROACTIVE_SOURCE_TYPE,
        )
        .order_by(ProactiveNotification.created_at.desc())
        .first()
    )


def build_briefing_items(
    db: Session,
    *,
    limit: int = 5,
    preferred_tickers: Optional[List[str]] = None,
    blocked_tickers: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    """Create a curated list of briefing items (Focus Score 우선, 공시/뉴스 보완)."""

    items: List[Dict[str, str]] = []

    # 1) Focus Score 상위 이벤트 우선
    focus_events = (
        db.query(FilingEvent)
        .filter(FilingEvent.derived_metrics.isnot(None))
        .order_by(func.coalesce((FilingEvent.derived_metrics["focus_score"]["total_score"]).as_integer(), 0).desc())
        .limit(limit * 2)
        .all()
    )
    for event in focus_events:
        if not _passes_ticker_filters(event.ticker, preferred_tickers, blocked_tickers):
            continue
        item = _event_item(event)
        score = _focus_score_value(event)
        if score is not None and score < 60:
            continue
        items.append(item)
        if len(items) >= limit:
            return items[:limit]

    # 2) 최근 공시로 보완
    filings = (
        db.query(Filing)
        .filter(Filing.filed_at.isnot(None))
        .order_by(Filing.filed_at.desc())
        .limit(max(1, limit // 2))
        .all()
    )
    for filing in filings:
        if not _passes_ticker_filters(filing.ticker, preferred_tickers, blocked_tickers):
            continue
        items.append(
            {
                "title": f"{filing.corp_name or filing.ticker or '기업'} 공시",
                "summary": getattr(filing, "report_name", None) or getattr(filing, "title", None),
                "ticker": filing.ticker,
                "targetUrl": f"/filings?filingId={filing.id}",
            }
        )
        if len(items) >= limit:
            return items[:limit]

    news_list = (
        db.query(NewsSignal)
        .filter(NewsSignal.detected_at.isnot(None))
        .order_by(NewsSignal.detected_at.desc())
        .limit(max(1, limit - len(items)))
        .all()
    )
    for news in news_list:
        if not _passes_ticker_filters(news.ticker, preferred_tickers, blocked_tickers):
            continue
        if any(_is_duplicate(item, news) for item in items):
            continue
        items.append(
            {
                "title": news.title or news.headline or "뉴스",
                "summary": news.summary or news.snippet,
                "ticker": news.ticker,
                "targetUrl": news.article_url or news.source_url,
            }
        )
        if len(items) >= limit:
            break

    return items[:limit]


def _event_item(event: FilingEvent) -> Dict[str, str]:
    derived = event.derived_metrics or {}
    focus = derived.get("focus_score") if isinstance(derived, dict) else None
    total, detail = _focus_summary(focus) if isinstance(focus, dict) else ("", "")
    summary_parts = []
    if event.report_name:
        summary_parts.append(event.report_name)
    elif event.event_name:
        summary_parts.append(event.event_name)
    if total:
        summary_parts.append(total)
    if detail:
        summary_parts.append(detail)
    summary_text = " · ".join(part for part in summary_parts if part)
    return {
        "title": event.event_name or event.report_name or "주요 이벤트",
        "summary": summary_text or None,
        "ticker": event.ticker,
        "targetUrl": f"/filings?receiptNo={event.receipt_no}",
    }


def _focus_summary(focus: Dict[str, object]) -> Tuple[str, str]:
    try:
        total_score = focus.get("total_score") or focus.get("totalScore")
        subs = focus.get("sub_scores") or focus.get("subScores") or {}
        impact = subs.get("impact") if isinstance(subs, dict) else None
        clarity = subs.get("clarity") if isinstance(subs, dict) else None
        consistency = subs.get("consistency") if isinstance(subs, dict) else None
        confirmation = subs.get("confirmation") if isinstance(subs, dict) else None
        total_label = f"Focus Score {int(total_score)}점" if total_score is not None else ""
        detail = (
            f"Impact {int(impact) if impact is not None else '-'} / "
            f"Clarity {int(clarity) if clarity is not None else '-'} / "
            f"Consistency {int(consistency) if consistency is not None else '-'} / "
            f"Confirmation {int(confirmation) if confirmation is not None else '-'}"
        )
        return total_label, detail
    except Exception:
        return "", ""


def _focus_score_value(event: FilingEvent) -> Optional[int]:
    derived = event.derived_metrics or {}
    focus = derived.get("focus_score") if isinstance(derived, dict) else None
    if isinstance(focus, dict):
        total = focus.get("total_score") or focus.get("totalScore")
        try:
            return int(total) if total is not None else None
        except (TypeError, ValueError):
            return None
    return None


def _passes_ticker_filters(
    ticker: Optional[str],
    preferred: Optional[List[str]],
    blocked: Optional[List[str]],
) -> bool:
    tick = (ticker or "").strip()
    if blocked and tick and tick in blocked:
        return False
    if preferred:
        # allow empty tickers if no preference matched
        if tick and tick not in preferred:
            return False
    return True


def _is_duplicate(existing: Dict[str, str], news: NewsSignal) -> bool:
    if not existing:
        return False
    title = (news.title or news.headline or "").strip().lower()
    url = (news.article_url or news.source_url or "").strip().lower()
    return (
        (existing.get("title") or "").strip().lower() == title
        or (existing.get("targetUrl") or "").strip().lower() == url
    )
