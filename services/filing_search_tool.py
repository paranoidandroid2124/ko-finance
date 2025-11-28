"""Tool executor for filing search.

Handles natural language filing search queries by:
1. Parsing entities (companies, years, report types)
2. Running a lightweight filings lookup (existing /filings logic)
3. Returning structured results for the in-chat confirmation card
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import urlencode

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models.filing import Filing
from models.summary import Summary
from services.filing_constants import REPORT_TYPE_LABELS
from services.filing_query_parser import FilingSearchParams, parse_filing_query

DEFAULT_LOOKBACK_DAYS = 30
MAX_RESULTS = 8


def _parse_date(value: Optional[str]) -> Optional[datetime.date]:
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(value)
    except ValueError:
        return None


def _date_range(params: FilingSearchParams) -> tuple[datetime.datetime, datetime.datetime]:
    today = datetime.datetime.utcnow().date()
    start_date = _parse_date(params.start_date) or (today - datetime.timedelta(days=DEFAULT_LOOKBACK_DAYS - 1))
    end_date = _parse_date(params.end_date) or today
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    start_dt = datetime.datetime.combine(start_date, datetime.time.min)
    end_dt = datetime.datetime.combine(end_date, datetime.time.max)
    return start_dt, end_dt


def _viewer_url(urls: Optional[Mapping[str, Any]]) -> Optional[str]:
    if not isinstance(urls, Mapping):
        return None
    for key in ("viewer", "pdf_viewer", "viewer_url", "download", "pdf"):
        candidate = urls.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _build_query(question: str, params: FilingSearchParams, db: Session):
    query = db.query(Filing)
    query = query.filter(Filing.filed_at.isnot(None))

    company_filters: List[Any] = []
    companies = [name for name in params.company_names if name]
    if companies:
        company_filters.append(Filing.corp_name.in_(companies))
        company_filters.append(Filing.ticker.in_(companies))
        company_filters.append(Filing.corp_code.in_(companies))
    if company_filters:
        query = query.filter(or_(*company_filters))

    if params.report_types:
        patterns = [REPORT_TYPE_LABELS.get(code, code) for code in params.report_types]
        report_filters = [Filing.report_name.ilike(f"%{pattern}%") for pattern in patterns]
        title_filters = [Filing.title.ilike(f"%{pattern}%") for pattern in patterns]
        query = query.filter(or_(*report_filters, *title_filters))

    normalized_question = (question or "").strip()
    if normalized_question and not companies:
        query = query.filter(
            or_(
                Filing.report_name.ilike(f"%{normalized_question}%"),
                Filing.title.ilike(f"%{normalized_question}%"),
                Filing.corp_name.ilike(f"%{normalized_question}%"),
                Filing.ticker.ilike(f"%{normalized_question}%"),
            )
        )

    start_dt, end_dt = _date_range(params)
    query = query.filter(Filing.filed_at >= start_dt, Filing.filed_at <= end_dt)

    return query.order_by(Filing.filed_at.desc(), Filing.created_at.desc())


def execute_filing_search(
    question: str,
    db: Session,
) -> Dict[str, Any]:
    """
    Execute a natural language filing search.

    Args:
        question: Natural language query (e.g., "2022년 삼성전자 사업보고서")
        db: Database session

    Returns:
        Dictionary with parsed params and lightweight search results for the confirmation card.
    """
    params = parse_filing_query(question)
    query_params: Dict[str, Any] = {}
    if params.start_date:
        query_params["start_date"] = params.start_date
    if params.end_date:
        query_params["end_date"] = params.end_date
    if params.company_names:
        query_params["company"] = params.company_names[0]
    if params.report_types:
        query_params["report_types"] = params.report_types

    query = _build_query(question, params, db).limit(MAX_RESULTS)
    filings: List[Filing] = list(query.all())
    summaries = (
        db.query(Summary).filter(Summary.filing_id.in_([filing.id for filing in filings])).all() if filings else []
    )
    summary_map = {entry.filing_id: entry for entry in summaries}

    results: List[Dict[str, Any]] = []
    for filing in filings:
        summary = summary_map.get(filing.id)
        viewer_url = _viewer_url(filing.urls)
        results.append(
            {
                "id": str(filing.id),
                "title": filing.report_name or filing.title,
                "company": filing.corp_name or filing.ticker,
                "ticker": filing.ticker,
                "corp_code": filing.corp_code,
                "filed_at": filing.filed_at.isoformat() if filing.filed_at else None,
                "category": filing.category,
                "analysis_status": filing.analysis_status,
                "sentiment": summary.sentiment_label if summary and summary.sentiment_label else None,
                "sentiment_reason": summary.sentiment_reason if summary else None,
                "insight_score": getattr(filing, "insight_score", None),
                "viewer_url": viewer_url,
                "download_url": filing.urls.get("download") if isinstance(filing.urls, Mapping) else None,
            }
        )

    archive_params = {}
    if params.company_names:
        archive_params["ticker"] = params.company_names[0]
    if params.start_date:
        archive_params["startDate"] = params.start_date
    if params.end_date:
        archive_params["endDate"] = params.end_date
    archive_url = f"/insights/filings?{urlencode(archive_params)}" if archive_params else "/insights/filings"

    payload: Dict[str, Any] = {
        "parsed_params": {
            "companies": params.company_names,
            "years": params.years,
            "start_date": params.start_date,
            "end_date": params.end_date,
            "report_types": params.report_types,
        },
        "query_params": query_params,
        "archive_url": archive_url,
        "results": results,
        "status": "ready_for_confirmation" if results else "no_results",
        "message": "검색 파라미터를 확인해주세요." if results else "조건에 맞는 공시를 찾지 못했습니다.",
    }
    return payload
