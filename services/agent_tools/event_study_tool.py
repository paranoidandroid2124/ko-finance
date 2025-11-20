"""Agent-facing helper that runs the event study analysis pipeline."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional, Sequence, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import SessionLocal
from models.event_study import EventRecord
from services import event_study_service
from services.event_study_windows import EventWindowPreset, get_event_window_preset


class EventStudyNotFoundError(ValueError):
    """Raised when the requested event study target could not be resolved."""


def _resolve_session(db: Optional[Session]) -> Tuple[Session, bool]:
    if db is not None:
        return db, False
    session = SessionLocal()
    return session, True


def _find_event_record(db: Session, ticker: str, event_date: Optional[date]) -> Optional[EventRecord]:
    query = (
        db.query(EventRecord)
        .filter(func.upper(EventRecord.ticker) == ticker.upper())
        .order_by(EventRecord.event_date.desc(), EventRecord.rcept_no.desc())
    )
    if event_date:
        query = query.filter(EventRecord.event_date == event_date)
    return query.first()


def generate_event_study_payload(
    *,
    ticker: str,
    event_date: Optional[date] = None,
    window_key: Optional[str] = None,
    window: Optional[int] = None,
    cap_buckets: Optional[Sequence[str]] = None,
    markets: Optional[Sequence[str]] = None,
    significance: Optional[float] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Return a condensed payload (metrics + detail) for a ticker event."""

    normalized_ticker = event_study_service.normalize_single_value(ticker)
    if not normalized_ticker:
        raise EventStudyNotFoundError("ticker is required")

    normalized_caps = event_study_service.normalize_str_list(cap_buckets)
    normalized_markets = event_study_service.normalize_str_list(markets)

    session, should_close = _resolve_session(db)
    try:
        event = _find_event_record(session, normalized_ticker, event_date)
        if not event:
            raise EventStudyNotFoundError(f"No event found for {normalized_ticker}")

        if window and window > 0:
            window_size = abs(int(window))
            preset = EventWindowPreset(
                key=f"custom_{window_size}",
                label=f"[-{window_size},+{window_size}]",
                start=-window_size,
                end=window_size,
                description="Custom symmetric event window",
                significance=significance or 0.1,
                is_default=False,
            )
        else:
            preset = get_event_window_preset(window_key, session)
        resolved_significance = significance if significance is not None else preset.significance

        cohort = event_study_service.compute_event_metrics(
            session,
            event_type=event.event_type,
            window=(preset.start, preset.end),
            ticker=normalized_ticker,
            markets=normalized_markets or None,
            cap_buckets=normalized_caps or None,
            significance=resolved_significance,
            min_samples=1,
        )
        if cohort is None:
            raise EventStudyNotFoundError("Not enough samples to compute metrics.")

        detail = event_study_service.load_event_detail(
            session,
            receipt_no=event.rcept_no,
            start=preset.start,
            end=preset.end,
        )

        events_response = event_study_service.fetch_event_rows(
            session,
            limit=5,
            offset=0,
            window_end=preset.end,
            event_types=[event.event_type],
            ticker=normalized_ticker,
            markets=normalized_markets or None,
            cap_buckets=normalized_caps or None,
            start_date=None,
            end_date=None,
            search_query=None,
        )

        metrics_block = {
            "sampleSize": cohort.n,
            "meanCaar": cohort.mean_caar,
            "hitRate": cohort.hit_rate,
            "ciLo": cohort.ci_lo,
            "ciHi": cohort.ci_hi,
            "pValue": cohort.p_value,
            "aar": cohort.aar,
            "caar": cohort.caar,
            "dist": cohort.dist,
        }

        return {
            "ticker": normalized_ticker,
            "eventType": event.event_type,
            "eventDate": event.event_date.isoformat() if event.event_date else None,
            "window": {
                "key": preset.key,
                "label": preset.label,
                "start": preset.start,
                "end": preset.end,
                "significance": resolved_significance,
            },
            "metrics": metrics_block,
            "eventDetail": detail.model_dump(by_alias=True) if detail else None,
            "recentEvents": events_response.model_dump(by_alias=True),
        }
    finally:
        if should_close:
            session.close()


__all__ = ["EventStudyNotFoundError", "generate_event_study_payload"]
