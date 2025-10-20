"""FastAPI routes exposing Market Mood data."""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.news import NewsObservation, NewsSignal
from schemas.api.news import NewsObservationResponse, NewsSignalResponse

router = APIRouter(prefix="/news", tags=["News"])


@router.get("/", response_model=List[NewsSignalResponse])
def list_news_signals(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """Return paginated news sentiment signals."""
    news_signals = (
        db.query(NewsSignal)
        .order_by(NewsSignal.published_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return news_signals


@router.get("/observations", response_model=List[NewsObservationResponse])
def list_news_observations(skip: int = 0, limit: int = 20, db: Session = Depends(get_db)):
    """Return aggregated Market Mood observations."""
    observations = (
        db.query(NewsObservation)
        .order_by(NewsObservation.window_start.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return observations

