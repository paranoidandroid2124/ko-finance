"\"\"\"Company snapshot endpoints delivering consolidated P0 insights.\"\"\""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Tuple

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
    EvidenceLink,
    EventItem,
    FilingHeadline,
    FinancialStatementBlock,
    FinancialStatementRow,
    FinancialValue,
    FiscalAlignmentInsight,
    KeyMetric,
    NewsWindowInsight,
    RestatementHighlight,
    SummaryBlock,
    TopicWeight,
    TimelinePoint,
    TimelineResponse,
)
from services.aggregation.news_metrics import compute_news_window_metrics
from services.aggregation import timeline_metrics
from core.logging import get_logger

router = APIRouter(prefix="/companies", tags=["Companies"])
logger = get_logger(__name__)

METRIC_DEFINITIONS: Sequence[Dict[str, Iterable[str]]] = (
    {"code": "roe", "label": "ROE", "keywords": ("roe", "return on equity")},
    {"code": "operating_margin", "label": "영업이익률", "keywords": ("영업이익률", "operating margin")},
    {"code": "debt_ratio", "label": "부채비율", "keywords": ("부채비율", "debt ratio")},
    {"code": "revenue_growth", "label": "매출액증가율", "keywords": ("매출액증가율", "sales growth")},
)

FINANCIAL_STATEMENTS: Sequence[Dict[str, Any]] = (
    {
        "statement_code": "income_statement",
        "label": "손익계산서",
        "rows": (
            {"metric_code": "revenue", "label": "매출액", "keywords": ("매출", "Revenue")},
            {"metric_code": "gross_profit", "label": "매출총이익", "keywords": ("매출총이익", "Gross profit")},
            {"metric_code": "operating_income", "label": "영업이익", "keywords": ("영업이익", "Operating income")},
            {"metric_code": "ebitda", "label": "EBITDA", "keywords": ("EBITDA",)},
            {"metric_code": "net_income", "label": "당기순이익", "keywords": ("당기순이익", "Net income")},
        ),
    },
    {
        "statement_code": "balance_sheet",
        "label": "대차대조표",
        "rows": (
            {"metric_code": "total_assets", "label": "자산총계", "keywords": ("자산총계", "Total assets")},
            {"metric_code": "total_liabilities", "label": "부채총계", "keywords": ("부채총계", "Total liabilities")},
            {"metric_code": "total_equity", "label": "자본총계", "keywords": ("자본총계", "Total equity")},
        ),
    },
    {
        "statement_code": "cash_flow",
        "label": "현금흐름표",
        "rows": (
            {
                "metric_code": "operating_cash_flow",
                "label": "영업활동현금흐름",
                "keywords": ("영업활동현금흐름", "Operating activities"),
            },
            {
                "metric_code": "investing_cash_flow",
                "label": "투자활동현금흐름",
                "keywords": ("투자활동현금흐름", "Investing activities"),
            },
            {
                "metric_code": "financing_cash_flow",
                "label": "재무활동현금흐름",
                "keywords": ("재무활동현금흐름", "Financing activities"),
            },
        ),
    },
)

RESTATEMENT_METRIC_PRIORITY: Sequence[str] = (
    "net_income",
    "operating_income",
    "revenue",
)

_PERIOD_ORDER = {
    "Q1": 1,
    "Q2": 2,
    "Q3": 3,
    "Q4": 4,
    "FY": 5,
}




def _resolve_company_context(
    db: Session,
    identifier: str,
) -> Tuple[Filing, str, str, str]:
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
    return latest_filing, corp_code, ticker, corp_name

@router.get("/{identifier}/snapshot", response_model=CompanySnapshotResponse)
def company_snapshot(identifier: str, db: Session = Depends(get_db)) -> CompanySnapshotResponse:
    """Return consolidated snapshot for a company identified by ticker or corp_code."""
    latest_filing, corp_code, ticker, corp_name = _resolve_company_context(db, identifier)

    summary_record = (
        db.query(Summary)
        .filter(Summary.filing_id == latest_filing.id)
        .order_by(Summary.created_at.desc())
        .first()
    )

    key_metrics = _collect_key_metrics(db, corp_code)
    financial_statements = _collect_financial_statements(db, corp_code)
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

    restatement_highlights = _collect_restatement_highlights(db, corp_code, limit=3)
    evidence_links = _build_evidence_links(financial_statements, limit=8)
    fiscal_alignment = _compute_fiscal_alignment(financial_statements)

    response = CompanySnapshotResponse(
        corp_code=corp_code,
        ticker=ticker,
        corp_name=corp_name,
        latest_filing=_build_filing_headline(latest_filing),
        summary=_build_summary_block(summary_record),
        financial_statements=financial_statements,
        key_metrics=key_metrics,
        major_events=event_models,
        news_signals=news_models,
        restatement_highlights=restatement_highlights,
        evidence_links=evidence_links,
        fiscal_alignment=fiscal_alignment,
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


def _format_period_label(value: Optional[FinancialValue]) -> str:
    if value is None:
        return ""
    year = value.fiscal_year
    period = (value.fiscal_period or "").upper()
    if value.period_type == "annual":
        if value.period_end_date:
            try:
                if isinstance(value.period_end_date, str):
                    end = datetime.fromisoformat(value.period_end_date)
                else:
                    end = value.period_end_date
                return f"{end.year}년 {end.month}월"
            except ValueError:
                pass
        return f"{year} FY" if year else "연도 미상"
    if value.period_type == "quarter":
        return f"{year} {period}" if year else period or "분기"
    return period or (f"{year}" if year else "기간 미상")


def _collect_financial_statements(db: Session, corp_code: str, max_points: int = 8) -> List[FinancialStatementBlock]:
    statements: List[FinancialStatementBlock] = []
    for statement in FINANCIAL_STATEMENTS:
        rows: List[FinancialStatementRow] = []
        for row in statement.get("rows", []):
            keywords = tuple(row.get("keywords") or (row.get("label"),))
            series = _select_metric_series(
                db,
                corp_code=corp_code,
                keywords=keywords,
                max_points=max_points,
            )
            if not series:
                continue
            values = [
                FinancialValue(
                    fiscal_year=record.fiscal_year,
                    fiscal_period=record.fiscal_period,
                    period_type=_infer_period_type(record.fiscal_period),
                    period_end_date=record.period_end_date,
                    value=record.value,
                    unit=record.unit,
                    currency=record.currency,
                    reference_no=record.reference_no,
                )
                for record in series
            ]
            if not values:
                continue
            rows.append(
                FinancialStatementRow(
                    metric_code=row.get("metric_code") or series[0].metric_code,
                    label=row.get("label") or series[0].metric_name,
                    values=values,
                )
            )
        if rows:
            statements.append(
                FinancialStatementBlock(
                    statement_code=statement.get("statement_code", "custom"),
                    label=statement.get("label", "Statement"),
                    rows=rows,
                    description=statement.get("description"),
                )
            )
    return statements


def _collect_restatement_highlights(db: Session, corp_code: str, limit: int = 3) -> List[RestatementHighlight]:
    if limit <= 0:
        return []

    corrections = (
        db.query(Filing)
        .filter(
            Filing.corp_code == corp_code,
            or_(
                Filing.category.in_(("correction", "revision", "정정 공시")),
                Filing.title.ilike("%정정%"),
                Filing.report_name.ilike("%정정%"),
            ),
            Filing.receipt_no.isnot(None),
        )
        .order_by(nulls_last(Filing.filed_at.desc()), Filing.created_at.desc())
        .limit(limit * 4)
    )

    highlights: List[RestatementHighlight] = []
    for filing in corrections:
        impact = _compute_restatement_metric_delta(db, filing)
        if not impact:
            continue
        highlights.append(
            RestatementHighlight(
                receipt_no=filing.receipt_no or "",
                title=filing.title or filing.report_name,
                filed_at=filing.filed_at.isoformat() if filing.filed_at else None,
                report_name=filing.report_name,
                metric_code=impact.get("metric_code"),
                metric_label=impact.get("metric_label"),
                previous_value=impact.get("previous_value"),
                current_value=impact.get("current_value"),
                delta_percent=impact.get("delta_percent"),
                viewer_url=_viewer_url(filing.receipt_no) if filing.receipt_no else None,
            )
        )
        if len(highlights) >= limit:
            break
    return highlights


def _compute_restatement_metric_delta(db: Session, filing: Filing) -> Optional[Dict[str, Any]]:
    if not filing.receipt_no or not filing.corp_code:
        return None

    metrics = (
        db.query(CorpMetric)
        .filter(
            CorpMetric.corp_code == filing.corp_code,
            CorpMetric.reference_no == filing.receipt_no,
        )
        .all()
    )
    if not metrics:
        return None

    metrics_by_code: Dict[str, CorpMetric] = {
        metric.metric_code: metric for metric in metrics if metric.metric_code
    }

    ordered_candidates = list(RESTATEMENT_METRIC_PRIORITY) + list(metrics_by_code.keys())
    for metric_code in ordered_candidates:
        metric = metrics_by_code.get(metric_code)
        if not metric or metric.value is None:
            continue
        previous = _previous_metric_record(db, metric)
        if not previous or previous.value in (None, 0):
            continue
        delta_percent = ((metric.value - previous.value) / abs(previous.value)) * 100
        return {
            "metric_code": metric.metric_code,
            "metric_label": metric.metric_name or metric.metric_code,
            "previous_value": previous.value,
            "current_value": metric.value,
            "delta_percent": delta_percent,
        }
    return None


def _previous_metric_record(db: Session, metric: CorpMetric) -> Optional[CorpMetric]:
    return (
        db.query(CorpMetric)
        .filter(
            CorpMetric.corp_code == metric.corp_code,
            CorpMetric.metric_code == metric.metric_code,
            CorpMetric.fiscal_year == metric.fiscal_year,
            CorpMetric.fiscal_period == metric.fiscal_period,
            CorpMetric.reference_no != metric.reference_no,
        )
        .order_by(
            nulls_last(CorpMetric.updated_at.desc()),
            nulls_last(CorpMetric.observed_at.desc()),
        )
        .first()
    )


def _build_evidence_links(
    statements: List[FinancialStatementBlock],
    limit: int = 8,
) -> List[EvidenceLink]:
    if limit <= 0:
        return []
    links: List[EvidenceLink] = []
    seen: set[Tuple[str, str]] = set()

    for block in statements:
        for row in block.rows:
            sorted_values = sorted(
                row.values,
                key=lambda value: (value.period_end_date or "", value.fiscal_year or 0),
                reverse=True,
            )
            for value in sorted_values:
                if not value.reference_no:
                    continue
                key = (row.metric_code, value.reference_no)
                if key in seen:
                    continue
                seen.add(key)
                links.append(
                    EvidenceLink(
                        statement_code=block.statement_code,
                        statement_label=block.label,
                        metric_code=row.metric_code,
                        metric_label=row.label,
                        period_label=_format_period_label(value),
                        reference_no=value.reference_no,
                        viewer_url=_viewer_url(value.reference_no),
                        value=value.value,
                        unit=value.unit,
                    )
                )
                break
        if len(links) >= limit:
            break
    return links[:limit]


def _compute_fiscal_alignment(
    statements: List[FinancialStatementBlock],
) -> Optional[FiscalAlignmentInsight]:
    if not statements:
        return None

    target_row = _find_metric_row(statements, "revenue")
    if not target_row:
        first_statement = statements[0] if statements else None
        target_row = first_statement.rows[0] if first_statement and first_statement.rows else None
    if not target_row:
        return None

    annual_values = [value for value in target_row.values if value.period_type == "annual"]
    quarter_values = [value for value in target_row.values if value.period_type == "quarter"]

    latest_annual = _latest_value(annual_values)
    latest_quarter = _latest_value(quarter_values)

    yoy_delta = None
    if latest_quarter and latest_quarter.fiscal_year is not None:
        comparator = next(
            (
                value
                for value in quarter_values
                if value.fiscal_period == latest_quarter.fiscal_period
                and (value.fiscal_year or 0) == (latest_quarter.fiscal_year or 0) - 1
            ),
            None,
        )
        if comparator and comparator.value not in (None, 0) and latest_quarter.value is not None:
            yoy_delta = ((latest_quarter.value - comparator.value) / abs(comparator.value)) * 100

    unique_quarters = {
        (value.fiscal_year, value.fiscal_period)
        for value in quarter_values
        if value.fiscal_period and value.fiscal_year is not None
    }
    quarter_coverage = len(unique_quarters)

    notes: List[str] = []
    if quarter_coverage >= 4 and yoy_delta is not None:
        alignment_status: Literal["good", "warning", "missing"] = "good"
    elif quarter_values or annual_values:
        alignment_status = "warning"
        if quarter_coverage < 4:
            notes.append("최근 4개 분기 데이터가 부족합니다.")
        if yoy_delta is None:
            notes.append("동일 분기 YoY 비교를 계산할 수 없습니다.")
    else:
        alignment_status = "missing"
        notes.append("재무 데이터가 충분하지 않습니다.")

    return FiscalAlignmentInsight(
        latest_annual_period=_format_period_label(latest_annual) if latest_annual else None,
        latest_quarter_period=_format_period_label(latest_quarter) if latest_quarter else None,
        yoy_delta_percent=yoy_delta,
        ttm_quarter_coverage=min(quarter_coverage, 12),
        alignment_status=alignment_status,
        notes=" ".join(notes) if notes else None,
    )


def _find_metric_row(
    statements: List[FinancialStatementBlock],
    metric_code: str,
) -> Optional[FinancialStatementRow]:
    for statement in statements:
        for row in statement.rows:
            if row.metric_code == metric_code:
                return row
    return None


def _latest_value(values: List[FinancialValue]) -> Optional[FinancialValue]:
    if not values:
        return None
    sorted_values = sorted(
        values,
        key=lambda value: (value.period_end_date or "", value.fiscal_year or 0),
        reverse=True,
    )
    return sorted_values[0]


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


def _select_metric_series(
    db: Session,
    corp_code: str,
    keywords: Sequence[str],
    *,
    max_points: int = 8,
) -> List[CorpMetric]:
    filters = []
    for keyword in keywords:
        keyword = (keyword or "").strip()
        if not keyword:
            continue
        filters.append(CorpMetric.metric_name.ilike(f"%{keyword}%"))
    if not filters:
        return []

    query = (
        db.query(CorpMetric)
        .filter(
            CorpMetric.corp_code == corp_code,
            CorpMetric.source.in_(("DE002", "DE003")),
            or_(*filters),
        )
        .order_by(
            nulls_last(CorpMetric.period_end_date.desc()),
            CorpMetric.fiscal_year.desc(),
            CorpMetric.fiscal_period.desc(),
            nulls_last(CorpMetric.updated_at.desc()),
        )
        .limit(max_points * 4)
    )
    records = query.all()
    deduped = _deduplicate_ordered_records(records, max_points=max_points)
    deduped.sort(key=lambda record: _period_sort_key(record.fiscal_year, record.fiscal_period))
    return deduped


def _deduplicate_ordered_records(records: Sequence[CorpMetric], *, max_points: int) -> List[CorpMetric]:
    seen: set[Tuple[Optional[int], Optional[str]]] = set()
    unique: List[CorpMetric] = []
    for record in records:
        key = (record.fiscal_year, record.fiscal_period)
        if key in seen:
            continue
        seen.add(key)
        unique.append(record)
        if len(unique) >= max_points:
            break
    return unique


def _period_sort_key(fiscal_year: Optional[int], fiscal_period: Optional[str]) -> Tuple[int, int]:
    year = fiscal_year or 0
    order = _PERIOD_ORDER.get((fiscal_period or "").upper(), 0)
    return (year, order)


def _infer_period_type(fiscal_period: Optional[str]) -> str:
    normalized = (fiscal_period or "").upper()
    if normalized in {"FY", "ANNUAL"}:
        return "annual"
    if normalized in {"Q1", "Q2", "Q3", "Q4"}:
        return "quarter"
    return "other"


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

@router.get("/{identifier}/timeline", response_model=TimelineResponse)
def company_timeline(
    identifier: str,
    window_days: int = Query(365, ge=7, le=365, description="Number of days to include in timeline"),
    db: Session = Depends(get_db),
) -> TimelineResponse:
    latest_filing, _, ticker, _ = _resolve_company_context(db, identifier)
    started_at = datetime.now(timezone.utc)

    raw_points = timeline_metrics.fetch_sentiment_timeline(
        db,
        ticker=ticker,
        window_days=window_days,
    )
    series = timeline_metrics.build_timeline_series(raw_points, max_points=min(window_days, 365))

    response = TimelineResponse(
        window_days=min(window_days, 365),
        total_points=series["total_points"],
        downsampled_points=series["downsampled_points"],
        points=[
            TimelinePoint(
                date=point["date"],
                sentiment_z=point.get("sentiment_z"),
                price_close=point.get("price_close"),
                volume=point.get("volume"),
                event_type=point.get("event_type"),
            )
            for point in series["points"]
        ],
    )

    latency_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
    logger.info(
        "Timeline generated for %s (window=%d, returned=%d/%d, latency_ms=%d)",
        ticker,
        response.window_days,
        response.downsampled_points,
        response.total_points,
        latency_ms,
    )
    return response
