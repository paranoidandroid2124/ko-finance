"\"\"\"Company snapshot endpoints delivering consolidated P0 insights.\"\"\""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, nulls_last, or_
from sqlalchemy.orm import Session

from database import get_db
from models.company import CorpMetric, FilingEvent
from models.filing import Filing
from models.news import NewsWindowAggregate
from models.summary import Summary
from schemas.api.company import (
    CompanySearchResult,
    CompanySnapshotResponse,
    CompanySuggestions,
    EventItem,
    FilingHeadline,
    KeyMetric,
    NewsWindowInsight,
    SummaryBlock,
    TopicWeight,
)
from services.aggregation.news_metrics import compute_news_window_metrics

router = APIRouter(prefix="/companies", tags=["Companies"])

METRIC_DEFINITIONS: Sequence[Dict[str, Iterable[str]]] = (
    {"code": "roe", "label": "ROE", "keywords": ("roe", "return on equity")},
    {"code": "operating_margin", "label": "영업이익률", "keywords": ("영업이익률", "operating margin")},
    {"code": "debt_ratio", "label": "부채비율", "keywords": ("부채비율", "debt ratio")},
    {"code": "revenue_growth", "label": "매출액증가율", "keywords": ("매출액증가율", "sales growth")},
)


@router.get("/{identifier}/snapshot", response_model=CompanySnapshotResponse)
def company_snapshot(identifier: str, db: Session = Depends(get_db)) -> CompanySnapshotResponse:
    """Return consolidated snapshot for a company identified by ticker or corp_code."""
    normalized = identifier.strip().upper()
    latest_filing = (
        db.query(Filing)
        .filter(or_(Filing.ticker == normalized, Filing.corp_code == normalized))
        .order_by(Filing.filed_at.desc().nullslast(), Filing.created_at.desc().nullslast())
        .first()
    )
    if not latest_filing:
        raise HTTPException(status_code=404, detail="Company not found.")

    corp_code = latest_filing.corp_code or normalized
    ticker = latest_filing.ticker or normalized
    corp_name = latest_filing.corp_name or ticker

    summary_record = (
        db.query(Summary)
        .filter(Summary.filing_id == latest_filing.id)
        .order_by(Summary.created_at.desc())
        .first()
    )

    key_metrics = _collect_key_metrics(db, corp_code)
    recent_events = _latest_events(db, corp_code, limit=8)
    news_metrics = _collect_news_metrics(db, ticker)

    event_models = [
        EventItem(
            id=event.id,
            event_type=event.event_type,
            event_name=event.event_name,
            event_date=event.event_date,
            resolution_date=event.resolution_date,
            report_name=event.report_name,
            derived_metrics=event.derived_metrics or {},
        )
        for event in recent_events
    ]

    news_models = [
        NewsWindowInsight(
            scope=record.scope,
            ticker=record.ticker,
            window_days=record.window_days,
            computed_for=record.computed_for,
            article_count=record.article_count,
            avg_sentiment=record.avg_sentiment,
            sentiment_z=record.sentiment_z,
            novelty_kl=record.novelty_kl,
            topic_shift=record.topic_shift,
            domestic_ratio=record.domestic_ratio,
            domain_diversity=record.domain_diversity,
            source_reliability=record.source_reliability,
            top_topics=[TopicWeight(**topic) for topic in (record.top_topics or [])],
        )
        for record in news_metrics
    ]

    response = CompanySnapshotResponse(
        corp_code=corp_code,
        ticker=ticker,
        corp_name=corp_name,
        latest_filing=_build_filing_headline(latest_filing),
        summary=_build_summary_block(summary_record),
        key_metrics=key_metrics,
        major_events=event_models,
        news_signals=news_models,
    )
    return response


@router.get("/search", response_model=List[CompanySearchResult])
def search_companies(
    q: str = Query(..., min_length=1, description="Company name, ticker, or corp code keyword"),
    limit: int = Query(8, ge=1, le=25),
    db: Session = Depends(get_db),
) -> List[CompanySearchResult]:
    keyword = q.strip()
    if not keyword:
        return []

    query = (
        db.query(Filing)
        .filter(
            or_(
                Filing.corp_name.ilike(f"%{keyword}%"),
                Filing.ticker.ilike(f"%{keyword}%"),
                Filing.corp_code.ilike(f"%{keyword}%"),
            )
        )
        .order_by(nulls_last(Filing.filed_at.desc()), Filing.created_at.desc())
        .limit(limit * 8)
    )

    results: List[CompanySearchResult] = []
    seen: set[str] = set()
    for filing in query:
        key = filing.corp_code or filing.ticker
        if not key or key in seen:
            continue
        seen.add(key)
        highlight = _derive_highlight(filing, keyword)
        results.append(_build_search_result(filing, highlight=highlight))
        if len(results) >= limit:
            break

    if not results:
        fallback = _recent_filings(db, limit)
        return fallback
    return results


@router.get("/suggestions", response_model=CompanySuggestions)
def company_suggestions(
    limit: int = Query(6, ge=3, le=12),
    db: Session = Depends(get_db),
) -> CompanySuggestions:
    recent = _recent_filings(db, limit=limit)
    trending = _trending_news(db, limit=limit)
    return CompanySuggestions(recent_filings=recent, trending_news=trending)


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------

def _build_filing_headline(filing: Filing) -> Optional[FilingHeadline]:
    if filing is None:
        return None
    return FilingHeadline(
        receipt_no=filing.receipt_no,
        report_name=filing.report_name,
        title=filing.title,
        filed_at=filing.filed_at,
        viewer_url=_viewer_url(filing.receipt_no) if filing.receipt_no else None,
    )


def _build_summary_block(summary: Optional[Summary]) -> Optional[SummaryBlock]:
    if summary is None:
        return None
    return SummaryBlock(
        insight=summary.insight,
        who=summary.who,
        what=summary.what,
        when=summary.when,
        where=summary.where,
        why=summary.why,
        how=summary.how,
    )


def _viewer_url(receipt_no: str) -> str:
    return f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}"


def _collect_key_metrics(db: Session, corp_code: str) -> List[KeyMetric]:
    results: List[KeyMetric] = []
    for definition in METRIC_DEFINITIONS:
        record = _select_metric_record(db, corp_code, tuple(definition["keywords"]))
        if not record:
            continue
        results.append(
            KeyMetric(
                metric_code=record.metric_code,
                label=definition["label"],
                value=record.value,
                unit=record.unit,
                fiscal_year=record.fiscal_year,
                fiscal_period=record.fiscal_period,
            )
        )
    return results


def _select_metric_record(db: Session, corp_code: str, keywords: Sequence[str]) -> Optional[CorpMetric]:
    filters = []
    for keyword in keywords:
        filters.append(CorpMetric.metric_name.ilike(f"%{keyword}%"))
    if not filters:
        return None
    query = (
        db.query(CorpMetric)
        .filter(
            CorpMetric.corp_code == corp_code,
            CorpMetric.source == "DE002",
            or_(*filters),
        )
        .order_by(
            CorpMetric.fiscal_year.desc(),
            nulls_last(CorpMetric.updated_at.desc()),
            nulls_last(CorpMetric.period_end_date.desc()),
        )
    )
    return query.first()


def _latest_events(db: Session, corp_code: str, limit: int = 8) -> List[FilingEvent]:
    return (
        db.query(FilingEvent)
        .filter(FilingEvent.corp_code == corp_code)
        .order_by(
            nulls_last(FilingEvent.event_date.desc()),
            FilingEvent.updated_at.desc(),
        )
        .limit(limit)
        .all()
    )


def _collect_news_metrics(db: Session, ticker: str) -> List[NewsWindowAggregate]:
    results: List[NewsWindowAggregate] = []
    now = datetime.now(timezone.utc)

    scopes = (("ticker", ticker), ("global", None))
    windows = (7, 30)

    for scope, scoped_ticker in scopes:
        for window_days in windows:
            record = (
                db.query(NewsWindowAggregate)
                .filter(
                    NewsWindowAggregate.scope == scope,
                    NewsWindowAggregate.ticker == scoped_ticker,
                    NewsWindowAggregate.window_days == window_days,
                )
                .order_by(NewsWindowAggregate.computed_for.desc())
                .first()
            )
            if record is None and scope == "ticker":
                record = compute_news_window_metrics(
                    db=db,
                    window_end=now,
                    window_days=window_days,
                    scope=scope,
                    ticker=scoped_ticker,
                )
            if record:
                results.append(record)
    results.sort(key=lambda record: (0 if record.scope == "ticker" else 1, record.window_days))
    results.sort(key=lambda record: (0 if record.scope == "ticker" else 1, record.window_days))
    return results


def _recent_filings(db: Session, limit: int) -> List[CompanySearchResult]:
    query = (
        db.query(Filing)
        .filter(Filing.filed_at.isnot(None))
        .order_by(nulls_last(Filing.filed_at.desc()), Filing.created_at.desc())
        .limit(limit * 12)
    )
    results: List[CompanySearchResult] = []
    seen: set[str] = set()
    for filing in query:
        key = filing.corp_code or filing.ticker
        if not key or key in seen:
            continue
        seen.add(key)
        results.append(
            _build_search_result(
                filing,
                highlight=f"{filing.report_name or '최근 공시'}",
            )
        )
        if len(results) >= limit:
            break
    return results


def _trending_news(db: Session, limit: int) -> List[CompanySearchResult]:
    subquery = (
        db.query(
            NewsWindowAggregate.ticker.label("ticker"),
            func.max(NewsWindowAggregate.computed_for).label("latest_at"),
        )
        .filter(
            NewsWindowAggregate.scope == "ticker",
            NewsWindowAggregate.window_days == 7,
            NewsWindowAggregate.ticker.isnot(None),
        )
        .group_by(NewsWindowAggregate.ticker)
        .subquery()
    )

    aggregates = (
        db.query(NewsWindowAggregate)
        .join(
            subquery,
            and_(
                NewsWindowAggregate.ticker == subquery.c.ticker,
                NewsWindowAggregate.computed_for == subquery.c.latest_at,
            ),
        )
        .order_by(NewsWindowAggregate.article_count.desc())
        .limit(limit * 8)
        .all()
    )

    tickers = [agg.ticker for agg in aggregates if agg.ticker]
    if not tickers:
        return []

    latest_filings_map = _latest_filings_for_tickers(db, tickers)

    results: List[CompanySearchResult] = []
    seen: set[str] = set()
    for aggregate in aggregates:
        ticker = aggregate.ticker
        if not ticker:
            continue
        filing = latest_filings_map.get(ticker)
        if not filing:
            continue
        key = filing.corp_code or filing.ticker
        if not key or key in seen:
            continue
        seen.add(key)
        highlight = f"최근 7일 기사 {aggregate.article_count}건"
        results.append(_build_search_result(filing, highlight=highlight))
        if len(results) >= limit:
            break
    return results


def _latest_filings_for_tickers(db: Session, tickers: Sequence[str]) -> Dict[str, Filing]:
    if not tickers:
        return {}
    query = (
        db.query(Filing)
        .filter(Filing.ticker.in_(tickers))
        .order_by(Filing.ticker, nulls_last(Filing.filed_at.desc()), Filing.created_at.desc())
    )
    latest: Dict[str, Filing] = {}
    for filing in query:
        if filing.ticker not in latest:
            latest[filing.ticker] = filing
    return latest


def _build_search_result(filing: Filing, highlight: Optional[str] = None) -> CompanySearchResult:
    return CompanySearchResult(
        corp_code=filing.corp_code,
        ticker=filing.ticker,
        corp_name=filing.corp_name,
        latest_report_name=filing.report_name,
        latest_filed_at=filing.filed_at,
        highlight=highlight,
    )


def _derive_highlight(filing: Filing, keyword: str) -> Optional[str]:
    normalized = keyword.lower()
    if filing.ticker and normalized in filing.ticker.lower():
        return "티커 일치"
    if filing.corp_code and normalized in filing.corp_code.lower():
        return "법인코드 일치"
    if filing.corp_name and normalized in filing.corp_name.lower():
        return "회사명 일치"
    if filing.report_name and normalized in filing.report_name.lower():
        return filing.report_name
    return None
