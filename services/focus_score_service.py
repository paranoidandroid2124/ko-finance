"""Compute and persist Focus Score for events."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Sequence, Tuple, Any

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from models.event_study import EventRecord, EventStudyResult, EventSummary
from models.filing import Filing
from models.news import NewsSignal
from models.security_metadata import SecurityMetadata
from services.event_study_windows import format_window_label, get_event_window_preset
from services.focus_score import (
    FocusScoreContext,
    FocusScoreInput,
    NewsArticle,
    calculate_focus_score,
)


def _latest_summary_map(db: Session, window_label: str) -> Dict[Tuple[str, str], EventSummary]:
    latest_subq = (
        db.query(
            EventSummary.event_type.label("event_type"),
            EventSummary.cap_bucket.label("cap_bucket"),
            func.max(EventSummary.asof).label("max_asof"),
        )
        .filter(EventSummary.window_key == window_label)
        .group_by(EventSummary.event_type, EventSummary.cap_bucket)
        .subquery()
    )
    rows = (
        db.query(EventSummary)
        .join(
            latest_subq,
            and_(
                EventSummary.event_type == latest_subq.c.event_type,
                EventSummary.cap_bucket == latest_subq.c.cap_bucket,
                EventSummary.asof == latest_subq.c.max_asof,
            ),
        )
        .filter(EventSummary.window_key == window_label)
        .all()
    )
    return {(row.event_type, row.cap_bucket or "ALL"): row for row in rows}


def _restatement_count(db: Session, corp_code: str, now: datetime) -> int:
    window_start = now - timedelta(days=365)
    return (
        db.query(Filing)
        .filter(
            Filing.corp_code == corp_code,
            Filing.filed_at.isnot(None),
            Filing.filed_at >= window_start,
            Filing.receipt_no.isnot(None),
            Filing.category.in_(("correction", "revision", "정정 공시")),
        )
        .count()
    )


def _news_articles(db: Session, ticker: Optional[str], event_date: Optional[datetime]) -> Sequence[NewsArticle]:
    if not ticker:
        return []
    window_end = event_date or datetime.now(timezone.utc)
    window_start = window_end - timedelta(days=1)
    rows = (
        db.query(NewsSignal)
        .filter(
            NewsSignal.ticker == ticker.upper(),
            NewsSignal.published_at >= window_start,
            NewsSignal.published_at <= window_end,
        )
        .all()
    )
    return [
        NewsArticle(
            reliability="high" if (row.source_reliability or 0) >= 0.75 else "medium" if (row.source_reliability or 0) >= 0.4 else "low",
            publisher=row.source,
        )
        for row in rows
    ]


def compute_focus_score_for_event(db: Session, event: EventRecord) -> Optional[Dict[str, Any]]:
    if not event:
        return None

    preset = get_event_window_preset(None, db)
    window_label = format_window_label(preset.start, preset.end)
    summary_map = _latest_summary_map(db, window_label)

    caar = (
        db.query(EventStudyResult.car)
        .filter(EventStudyResult.rcept_no == event.rcept_no, EventStudyResult.t == preset.end)
        .scalar()
    )

    cap_bucket = (event.cap_bucket if event else None) or "ALL"
    summary = summary_map.get((event.event_type, cap_bucket)) or summary_map.get((event.event_type, "ALL"))
    p_value = float(summary.p_value) if summary and summary.p_value is not None else None

    now = datetime.now(timezone.utc)
    restatement_count = _restatement_count(db, event.corp_code, now) if event.corp_code else 0
    
    event_dt = None
    if event.event_date:
        event_dt = datetime.combine(event.event_date, datetime.min.time()).replace(tzinfo=timezone.utc)

    articles = _news_articles(db, event.ticker, event_dt)

    # Clarity fields: check metadata or derived fields
    # EventRecord has 'metadata' which is a dict.
    event_meta = event.metadata or {}
    present_fields = set(event_meta.keys())
    required_fields = {"issue_price", "new_shares"} if (event.event_type or "").upper() in {"SEO", "CONVERTIBLE"} else set()

    # Heuristic for summary length from corp_name + event_type since we don't have full text here easily
    # Ideally we'd fetch the Filing to get report_name, but EventRecord has corp_name/event_type.
    summary_chars = len((event.corp_name or "") + (event.event_type or "")) 
    # If we want better accuracy, we could join Filing, but let's keep it simple for now or fetch Filing if needed.
    
    ctx = FocusScoreContext(
        caar_distribution=[],  # optional: inject from cache if available
        stddev_distribution=[],
        restatement_count_1y=restatement_count,
        required_fields=required_fields,
        present_fields=present_fields,
        is_delayed=False,
        summary_chars=summary_chars,
        min_summary_chars=20, # Lowered threshold as we don't have full text
        articles=articles,
    )

    fs_input = FocusScoreInput(
        event_type=event.event_type or "UNKNOWN",
        cap_bucket=cap_bucket,
        caar=float(caar) if caar is not None else None,
        p_value=p_value,
        past_caar_stddev=None,
    )

    return calculate_focus_score(fs_input, ctx)


def persist_focus_score(db: Session, event: EventRecord, focus_score: Dict[str, Any]) -> None:
    # Update metadata
    meta = dict(event.metadata or {})
    meta["focus_score"] = focus_score
    event.metadata = meta # type: ignore[assignment]
    
    # Also update the top-level score column with the total score (normalized to 0-1 if needed, or just keep as is?)
    # EventRecord.score is currently 0.0-1.0 heuristic. Focus Score is 0-100.
    # Let's normalize it to 0.0-1.0 for consistency with existing score field usage, 
    # OR we can decide that EventRecord.score IS the Focus Score now.
    # Given the heuristic was 0-1, let's normalize.
    total = focus_score.get("total_score", 0)
    event.score = total / 100.0
    
    db.add(event)


def compute_and_persist_focus_score(db: Session, receipt_no: str) -> Optional[Dict[str, Any]]:
    event = db.query(EventRecord).filter(EventRecord.rcept_no == receipt_no).first()
    if not event:
        return None
    score = compute_focus_score_for_event(db, event)
    if score is None:
        return None
    persist_focus_score(db, event, score)
    db.commit()
    return score


def compute_focus_score_for_all(db: Session) -> int:
    events = db.query(EventRecord).all()
    updated = 0
    for event in events:
        score = compute_focus_score_for_event(db, event)
        if score is None:
            continue
        persist_focus_score(db, event, score)
        updated += 1
    if updated:
        db.commit()
    return updated
