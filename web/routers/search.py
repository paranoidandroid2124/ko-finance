"""Aggregated search endpoint exposing filings, news, tables, and charts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence, Set

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from database import get_db
from models.company import CorpMetric
from models.filing import Filing
from models.news import NewsSignal, NewsWindowAggregate
from schemas.api.search import (
    SearchEvidenceCounts,
    SearchResponse,
    SearchResult,
    SearchResultActions,
    SearchTotals,
)
from services.plan_service import PlanContext
from web.deps import get_plan_context

router = APIRouter(prefix="/search", tags=["Search"])

DEFAULT_LIMIT = 6
VALID_RESULT_TYPES = {"filing", "news", "table", "chart"}
FALLBACK_CATEGORY = "General"


@dataclass(slots=True)
class TableSummary:
    id: str
    corp_code: str | None
    ticker: str | None
    corp_name: str | None
    metric_count: int
    latest_observed_at: datetime | None


@dataclass(slots=True)
class ChartSummary:
    id: str
    ticker: str | None
    corp_name: str | None
    corp_code: str | None
    scope: str | None
    article_count: int
    computed_for: datetime | None
    source_reliability: float | None


@dataclass(slots=True)
class CountContext:
    filing_by_corp: dict[str, int]
    filing_by_ticker: dict[str, int]
    news_by_ticker: dict[str, int]
    reliability_by_ticker: dict[str, float]


@router.get("", response_model=SearchResponse)
def aggregated_search(
    q: str | None = Query(None, description="검색 키워드"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=50, description="타입별 최대 결과 수"),
    offset: int = Query(0, ge=0, description="타입별 페이지 오프셋"),
    types: list[str] | None = Query(None, description="요청할 결과 타입 (filing, news, table, chart)"),
    db: Session = Depends(get_db),
    plan: PlanContext = Depends(get_plan_context),
) -> SearchResponse:
    keyword = (q or "").strip()
    requested_types = _normalize_types(types)

    filings, filing_total = _fetch_filings(db, keyword, limit=limit, offset=offset, include_results="filing" in requested_types)
    news_items, news_total = _fetch_news(db, keyword, limit=limit, offset=offset, include_results="news" in requested_types)
    tables, table_total = _fetch_tables(db, keyword, limit=limit, offset=offset, include_results="table" in requested_types)
    charts, chart_total = _fetch_charts(db, keyword, limit=limit, offset=offset, include_results="chart" in requested_types)

    context = _collect_counts(db, filings, news_items, tables, charts)

    results = _build_results(
        filings if "filing" in requested_types else [],
        news_items if "news" in requested_types else [],
        tables if "table" in requested_types else [],
        charts if "chart" in requested_types else [],
        context,
        plan,
    )

    totals = SearchTotals(
        filing=filing_total,
        news=news_total,
        table=table_total,
        chart=chart_total,
    )

    return SearchResponse(query=keyword, total=len(results), totals=totals, results=results)


def _normalize_types(types: list[str] | None) -> Set[str]:
    if not types:
        return set(VALID_RESULT_TYPES)
    normalized = {value.strip().lower() for value in types if value}
    filtered = normalized & VALID_RESULT_TYPES
    if not filtered:
        return set(VALID_RESULT_TYPES)
    return filtered


def _fetch_filings(
    db: Session,
    keyword: str,
    *,
    limit: int,
    offset: int,
    include_results: bool,
) -> tuple[list[Filing], int]:
    query = db.query(Filing)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                Filing.report_name.ilike(pattern),
                Filing.title.ilike(pattern),
                Filing.corp_name.ilike(pattern),
                Filing.ticker.ilike(pattern),
                Filing.receipt_no.ilike(pattern),
            )
        )
    total = query.order_by(None).count()
    if not include_results:
        return [], total

    ordered = query.order_by(func.coalesce(Filing.filed_at, Filing.created_at).desc())
    rows = ordered.offset(offset).limit(limit).all()
    return list(rows), total


def _fetch_news(
    db: Session,
    keyword: str,
    *,
    limit: int,
    offset: int,
    include_results: bool,
) -> tuple[list[NewsSignal], int]:
    query = db.query(NewsSignal)
    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                NewsSignal.headline.ilike(pattern),
                NewsSignal.summary.ilike(pattern),
                NewsSignal.source.ilike(pattern),
                NewsSignal.ticker.ilike(pattern),
            )
        )
    total = query.order_by(None).count()
    if not include_results:
        return [], total

    ordered = query.order_by(NewsSignal.published_at.desc())
    rows = ordered.offset(offset).limit(limit).all()
    return list(rows), total


def _fetch_tables(
    db: Session,
    keyword: str,
    *,
    limit: int,
    offset: int,
    include_results: bool,
) -> tuple[list[TableSummary], int]:
    metric_count = func.count(CorpMetric.id).label("metric_count")
    latest_observed = func.max(CorpMetric.observed_at).label("latest_observed")
    latest_updated = func.max(CorpMetric.updated_at).label("latest_updated")

    query = (
        db.query(
            CorpMetric.corp_code,
            CorpMetric.corp_name,
            CorpMetric.ticker,
            metric_count,
            latest_observed,
            latest_updated,
        )
        .group_by(CorpMetric.corp_code, CorpMetric.corp_name, CorpMetric.ticker)
    )

    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                CorpMetric.corp_name.ilike(pattern),
                CorpMetric.ticker.ilike(pattern),
                CorpMetric.metric_name.ilike(pattern),
            )
        )

    total = query.order_by(None).count()
    if not include_results:
        return [], total

    ordered = query.order_by(latest_observed.desc().nullslast(), latest_updated.desc().nullslast())
    rows = ordered.offset(offset).limit(limit).all()

    summaries: list[TableSummary] = []
    for index, (corp_code, corp_name, ticker, count_value, observed_at, updated_at) in enumerate(rows, start=1):
        metric_total = int(count_value or 0)
        latest = observed_at or updated_at
        summaries.append(
            TableSummary(
                id=f"table-{corp_code or ticker or index}",
                corp_code=corp_code,
                ticker=ticker,
                corp_name=corp_name,
                metric_count=metric_total,
                latest_observed_at=latest,
            )
        )
    return summaries, total


def _fetch_charts(
    db: Session,
    keyword: str,
    *,
    limit: int,
    offset: int,
    include_results: bool,
) -> tuple[list[ChartSummary], int]:
    latest_table = (
        db.query(
            NewsWindowAggregate.ticker.label("ticker"),
            func.max(NewsWindowAggregate.computed_for).label("latest_for"),
        )
        .filter(NewsWindowAggregate.scope == "ticker")
        .filter(NewsWindowAggregate.ticker.isnot(None))
        .group_by(NewsWindowAggregate.ticker)
        .subquery()
    )

    query = (
        db.query(
            NewsWindowAggregate.id.label("agg_id"),
            NewsWindowAggregate.ticker.label("ticker"),
            NewsWindowAggregate.scope.label("scope"),
            NewsWindowAggregate.article_count.label("article_count"),
            NewsWindowAggregate.source_reliability.label("source_reliability"),
            NewsWindowAggregate.computed_for.label("computed_for"),
            func.max(Filing.corp_name).label("corp_name"),
            func.max(Filing.corp_code).label("corp_code"),
        )
        .join(
            latest_table,
            and_(
                NewsWindowAggregate.ticker == latest_table.c.ticker,
                NewsWindowAggregate.computed_for == latest_table.c.latest_for,
            ),
        )
        .outerjoin(Filing, Filing.ticker == NewsWindowAggregate.ticker)
    )

    if keyword:
        pattern = f"%{keyword}%"
        query = query.filter(
            or_(
                NewsWindowAggregate.ticker.ilike(pattern),
                Filing.corp_name.ilike(pattern),
                Filing.corp_code.ilike(pattern),
            )
        )

    query = query.group_by(
        NewsWindowAggregate.id,
        NewsWindowAggregate.ticker,
        NewsWindowAggregate.scope,
        NewsWindowAggregate.article_count,
        NewsWindowAggregate.source_reliability,
        NewsWindowAggregate.computed_for,
    )

    total = query.order_by(None).count()
    if not include_results:
        return [], total

    ordered = query.order_by(NewsWindowAggregate.article_count.desc())
    rows = ordered.offset(offset).limit(limit).all()

    summaries: list[ChartSummary] = []
    for row in rows:
        summaries.append(
            ChartSummary(
                id=f"chart-{row.agg_id}",
                ticker=row.ticker,
                corp_name=row.corp_name,
                corp_code=row.corp_code,
                scope=row.scope,
                article_count=int(row.article_count or 0),
                computed_for=row.computed_for,
                source_reliability=row.source_reliability,
            )
        )
    return summaries, total


def _collect_counts(
    db: Session,
    filings: Sequence[Filing],
    news_items: Sequence[NewsSignal],
    tables: Sequence[TableSummary],
    charts: Sequence[ChartSummary],
) -> CountContext:
    corp_codes = {item.corp_code for item in filings if item.corp_code}
    tickers = {item.ticker for item in filings if item.ticker}

    for article in news_items:
        if article.ticker:
            tickers.add(article.ticker)

    for table in tables:
        if table.corp_code:
            corp_codes.add(table.corp_code)
        if table.ticker:
            tickers.add(table.ticker)

    for chart in charts:
        if chart.corp_code:
            corp_codes.add(chart.corp_code)
        if chart.ticker:
            tickers.add(chart.ticker)

    filing_by_corp: dict[str, int] = {}
    if corp_codes:
        rows = (
            db.query(Filing.corp_code, func.count(Filing.id))
            .filter(Filing.corp_code.in_(list(corp_codes)))
            .group_by(Filing.corp_code)
            .all()
        )
        for corp_code, count in rows:
            if corp_code:
                filing_by_corp[corp_code] = int(count or 0)

    filing_by_ticker: dict[str, int] = {}
    if tickers:
        rows = (
            db.query(Filing.ticker, func.count(Filing.id))
            .filter(Filing.ticker.isnot(None))
            .filter(Filing.ticker.in_(list(tickers)))
            .group_by(Filing.ticker)
            .all()
        )
        for ticker, count in rows:
            if ticker:
                filing_by_ticker[ticker] = int(count or 0)

    news_by_ticker: dict[str, int] = {}
    reliability_by_ticker: dict[str, float] = {}
    if tickers:
        news_rows = (
            db.query(NewsSignal.ticker, func.count(NewsSignal.id))
            .filter(NewsSignal.ticker.isnot(None))
            .filter(NewsSignal.ticker.in_(list(tickers)))
            .group_by(NewsSignal.ticker)
            .all()
        )
        for ticker, count in news_rows:
            if ticker:
                news_by_ticker[ticker] = int(count or 0)

        reliability_rows = (
            db.query(NewsSignal.ticker, func.avg(NewsSignal.source_reliability))
            .filter(NewsSignal.ticker.isnot(None))
            .filter(NewsSignal.ticker.in_(list(tickers)))
            .group_by(NewsSignal.ticker)
            .all()
        )
        for ticker, score in reliability_rows:
            if ticker and score is not None:
                reliability_by_ticker[ticker] = float(score)

    return CountContext(
        filing_by_corp=filing_by_corp,
        filing_by_ticker=filing_by_ticker,
        news_by_ticker=news_by_ticker,
        reliability_by_ticker=reliability_by_ticker,
    )


def _build_results(
    filings: Sequence[Filing],
    news_items: Sequence[NewsSignal],
    tables: Sequence[TableSummary],
    charts: Sequence[ChartSummary],
    context: CountContext,
    plan: PlanContext,
) -> list[SearchResult]:
    ranked: list[tuple[datetime, SearchResult]] = []

    for filing in filings:
        timestamp = filing.updated_at or filing.filed_at or filing.created_at
        counts = _build_evidence_counts(
            filings=_lookup_count(filing.corp_code, context.filing_by_corp) or _lookup_count(filing.ticker, context.filing_by_ticker),
            news=_lookup_count(filing.ticker, context.news_by_ticker),
        )
        result = SearchResult(
            id=str(filing.id),
            type="filing",
            title=_build_filing_title(filing),
            category=_normalize_category(filing.category, filing.market),
            filedAt=_format_date(filing.filed_at),
            latestIngestedAt=_format_relative_time(timestamp),
            sourceReliability=_lookup_reliability(filing.ticker, context.reliability_by_ticker),
            evidenceCounts=counts,
            actions=_plan_actions("filing", plan),
        )
        ranked.append((_normalize_timestamp(timestamp), result))

    for article in news_items:
        timestamp = article.published_at or article.updated_at or article.created_at
        counts = _build_evidence_counts(
            news=_lookup_count(article.ticker, context.news_by_ticker),
            filings=_lookup_count(article.ticker, context.filing_by_ticker),
        )
        result = SearchResult(
            id=str(article.id),
            type="news",
            title=article.headline,
            category=article.source or FALLBACK_CATEGORY,
            filedAt=_format_date(article.published_at),
            latestIngestedAt=_format_relative_time(timestamp),
            sourceReliability=article.source_reliability
            if isinstance(article.source_reliability, (int, float))
            else _lookup_reliability(article.ticker, context.reliability_by_ticker),
            evidenceCounts=counts,
            actions=_plan_actions("news", plan),
        )
        ranked.append((_normalize_timestamp(timestamp), result))

    for table in tables:
        timestamp = table.latest_observed_at
        counts = _build_evidence_counts(
            tables=table.metric_count,
            filings=_lookup_count(table.corp_code, context.filing_by_corp) or _lookup_count(table.ticker, context.filing_by_ticker),
            news=_lookup_count(table.ticker, context.news_by_ticker),
        )
        title = f"{table.corp_name or table.ticker or '데이터'} 재무 테이블"
        result = SearchResult(
            id=table.id,
            type="table",
            title=title,
            category="재무 데이터",
            latestIngestedAt=_format_relative_time(timestamp),
            evidenceCounts=counts,
            actions=_plan_actions("table", plan),
        )
        ranked.append((_normalize_timestamp(timestamp), result))

    for chart in charts:
        timestamp = chart.computed_for
        counts = _build_evidence_counts(
            charts=chart.article_count,
            news=_lookup_count(chart.ticker, context.news_by_ticker),
            filings=_lookup_count(chart.corp_code, context.filing_by_corp) or _lookup_count(chart.ticker, context.filing_by_ticker),
        )
        label = chart.corp_name or chart.ticker or chart.scope or "차트"
        result = SearchResult(
            id=chart.id,
            type="chart",
            title=f"{label} 신호 추세",
            category="뉴스 감성" if (chart.scope or "") == "ticker" else (chart.scope or "차트"),
            latestIngestedAt=_format_relative_time(timestamp),
            sourceReliability=chart.source_reliability,
            evidenceCounts=counts,
            actions=_plan_actions("chart", plan),
        )
        ranked.append((_normalize_timestamp(timestamp), result))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [entry for _, entry in ranked]


def _lookup_count(key: str | None, mapping: dict[str, int]) -> int | None:
    if not key:
        return None
    return mapping.get(key)


def _lookup_reliability(key: str | None, mapping: dict[str, float]) -> float | None:
    if not key:
        return None
    return mapping.get(key)


def _build_evidence_counts(**values: int | None) -> SearchEvidenceCounts | None:
    filtered = {name: count for name, count in values.items() if isinstance(count, int) and count > 0}
    if not filtered:
        return None
    return SearchEvidenceCounts(**filtered)


def _plan_actions(result_type: str, plan: PlanContext) -> SearchResultActions:
    compare_allowed = plan.allows("search.compare")
    alert_allowed = plan.allows("search.alerts")
    export_allowed = plan.allows("search.export")

    if result_type == "filing":
        return SearchResultActions(
            compareLocked=not compare_allowed,
            alertLocked=not alert_allowed,
            exportLocked=not export_allowed,
        )
    if result_type == "news":
        return SearchResultActions(
            compareLocked=not compare_allowed,
            alertLocked=not alert_allowed,
            exportLocked=not export_allowed,
        )
    if result_type == "table":
        return SearchResultActions(
            compareLocked=True,
            alertLocked=True,
            exportLocked=False,
        )
    if result_type == "chart":
        return SearchResultActions(
            compareLocked=True,
            alertLocked=not alert_allowed,
            exportLocked=True,
        )
    return SearchResultActions(compareLocked=True, alertLocked=True, exportLocked=True)


def _build_filing_title(filing: Filing) -> str:
    for field in (filing.report_name, filing.title, filing.corp_name, filing.ticker):
        if field:
            return field
    return "Filing"


def _normalize_category(*candidates: str | None) -> str:
    for value in candidates:
        if value and value.strip():
            return value.strip()
    return FALLBACK_CATEGORY


def _format_date(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%d")


def _format_relative_time(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = _normalize_timestamp(value)
    now = datetime.now(timezone.utc)
    delta = now - normalized
    seconds = int(delta.total_seconds())
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _normalize_timestamp(value: datetime | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
