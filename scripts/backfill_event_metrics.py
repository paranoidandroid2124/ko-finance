"""Backfill per-event metrics (CAAR/p-value) into filing_events. 

This script pulls:
- CAAR: from event_study table at the default event window end (EventWindow preset if present, else fallback [-5,+20]).
- p_value: from the latest EventSummary matched by (event_type, cap_bucket) and the default window key.

Usage:
  python scripts/backfill_event_metrics.py
  python scripts/backfill_event_metrics.py --window-key window_short   # optional
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from typing import Dict, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from database import SessionLocal
from models.company import FilingEvent
from models.event_study import EventRecord, EventStudyResult, EventSummary
from services.event_study_windows import format_window_label, get_event_window_preset


def _load_window(db: Session, window_key: str | None) -> Tuple[int, int, str]:
    preset = get_event_window_preset(window_key, db)
    return preset.start, preset.end, format_window_label(preset.start, preset.end)


def _latest_summaries(db: Session, window_label: str) -> Dict[Tuple[str, str], Dict[str, float]]:
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
            (
                (EventSummary.event_type == latest_subq.c.event_type)
                & (EventSummary.cap_bucket == latest_subq.c.cap_bucket)
                & (EventSummary.asof == latest_subq.c.max_asof)
            ),
        )
        .filter(EventSummary.window_key == window_label)
        .all()
    )

    summary_map: Dict[Tuple[str, str], Dict[str, float]] = {}
    for row in rows:
        key = (row.event_type, row.cap_bucket or "ALL")
        summary_map[key] = {
            "p_value": float(row.p_value) if row.p_value is not None else None,
            "mean_caar": float(row.mean_caar) if row.mean_caar is not None else None,
        }
    return summary_map


def backfill(window_key: str | None = None) -> int:
    updated = 0
    with SessionLocal() as db:
        start, end, window_label = _load_window(db, window_key)
        summaries = _latest_summaries(db, window_label)

        # preload CAAR at window end for all events
        caar_map: Dict[str, float] = {}
        series_rows = (
            db.query(EventStudyResult)
            .filter(EventStudyResult.t == end)
            .all()
        )
        for row in series_rows:
            if row.car is not None:
                caar_map[row.rcept_no] = float(row.car)

        # preload cap_bucket by receipt_no from EventRecord (if exists)
        cap_map: Dict[str, str] = {row.rcept_no: (row.cap_bucket or "ALL") for row in db.query(EventRecord).all()}

        # process filing events
        events = db.query(FilingEvent).all()
        for event in events:
            derived = dict(event.derived_metrics or {})
            changed = False

            # inject CAAR if available
            if event.receipt_no in caar_map and derived.get("caar") is None:
                derived["caar"] = caar_map[event.receipt_no]
                changed = True

            # inject p_value from cohort summary
            event_type = event.event_type or ""
            cap_bucket = cap_map.get(event.receipt_no, "ALL")
            p_val = None
            if (event_type, cap_bucket) in summaries:
                p_val = summaries[(event_type, cap_bucket)].get("p_value")
            if p_val is None and (event_type, "ALL") in summaries:
                p_val = summaries[(event_type, "ALL")].get("p_value")
            if p_val is not None and derived.get("p_value") is None:
                derived["p_value"] = p_val
                changed = True

            if changed:
                event.derived_metrics = derived
                updated += 1

        if updated:
            db.commit()
    return updated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill derived_metrics for filing_events.")
    parser.add_argument("--window-key", dest="window_key", default=None, help="event_windows.key (default: DB preset or fallback)")
    args = parser.parse_args()
    count = backfill(args.window_key)
    print(f"Updated {count} filing_events with CAAR/p_value.")
