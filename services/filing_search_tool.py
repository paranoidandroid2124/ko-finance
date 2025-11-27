"""Tool executor for filing search.

Handles natural language filing search queries by:
1. Parsing entities (companies, years, report types)
2. Returning structured results for the confirmation card
"""

from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Session

from services.filing_query_parser import FilingSearchParams, parse_filing_query


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
        Dictionary with parsed params for confirmation card:
        {
            "parsed_params": {...},
            "query_params": {...},
            "status": "ready_for_confirmation"
        }
    """
    # Parse the query
    params = parse_filing_query(question)
    
    # Build query parameters for URL
    query_params = {}
    if params.start_date:
        query_params["start_date"] = params.start_date
    if params.end_date:
        query_params["end_date"] = params.end_date
    
    return {
        "parsed_params": {
            "companies": params.company_names,
            "years": params.years,
            "start_date": params.start_date,
            "end_date": params.end_date,
            "report_types": params.report_types,
        },
        "query_params": query_params,
        "status": "ready_for_confirmation",
        "message": "검색 파라미터를 확인해주세요.",
    }
