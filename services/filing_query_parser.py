"""Entity parser for natural language filing queries.

Extracts companies, years, and report types from user queries like:
- "2022년 삼성전자 사업보고서"
- "삼전이랑 하닉 최근 3년 정기보고서"
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel

from services.filing_constants import REPORT_TYPE_MAP


# Common company name aliases (will be replaced by cache)
COMPANY_ALIASES = {
    "삼전": "삼성전자",
    "삼성": "삼성전자",
    "하닉": "SK하이닉스",
    "하이닉스": "SK하이닉스",
    "네이버": "NAVER",
    "카카오": "카카오",
}


class FilingSearchParams(BaseModel):
    """Parsed parameters from a natural language filing query."""

    companies: List[str] = []  # Corp codes or tickers
    company_names: List[str] = []  # Display names
    years: List[int] = []
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None  # YYYY-MM-DD
    report_types: List[str] = []


def parse_filing_query(question: str) -> FilingSearchParams:
    """
    Extract entities from natural language filing query.
    
    Examples:
        "2022년 삼성전자 사업보고서" → companies=["삼성전자"], years=[2022], types=["annual"]
        "삼전 21~23년 정기보고서" → companies=["삼성전자"], years=[2021,2022,2023]
    """
    params = FilingSearchParams()
    
    # Extract years
    params.years = _extract_years(question)
    if params.years:
        # Convert years to date range
        params.start_date = f"{min(params.years)}-01-01"
        params.end_date = f"{max(params.years)}-12-31"
    
    # Extract companies
    params.company_names = _extract_companies(question)
    
    # Extract report types
    params.report_types = _extract_report_types(question)
    
    return params


def _extract_years(text: str) -> List[int]:
    """
    Extract years from text.
    
    Patterns:
    - "2022년" → [2022]
    - "21년" → [2021]
    - "21~23년" → [2021, 2022, 2023]
    - "최근 3년" → [current_year-2, current_year-1, current_year]
    """
    years = []
    
    # Pattern: "21~23년" or "2021~2023년"
    range_match = re.search(r"(\d{2,4})\s*~\s*(\d{2,4})\s*년", text)
    if range_match:
        start_year = _normalize_year(int(range_match.group(1)))
        end_year = _normalize_year(int(range_match.group(2)))
        return list(range(start_year, end_year + 1))
    
    # Pattern: "최근 N년"
    recent_match = re.search(r"최근\s*(\d+)\s*년", text)
    if recent_match:
        n = int(recent_match.group(1))
        current_year = datetime.now().year
        return list(range(current_year - n + 1, current_year + 1))
    
    # Pattern: "2022년" or "21년"
    year_matches = re.findall(r"(\d{2,4})\s*년", text)
    for match in year_matches:
        year = _normalize_year(int(match))
        if year not in years:
            years.append(year)
    
    return sorted(years)


def _normalize_year(year: int) -> int:
    """Convert 2-digit year to 4-digit (21 → 2021)."""
    if year < 100:
        if year > 50:
            return 1900 + year
        else:
            return 2000 + year
    return year


def _extract_companies(text: str) -> List[str]:
    """
    Extract company names from text using the global company cache.
    
    Handles:
    - Common aliases: "삼전" → "삼성전자"  
    - Full names: "삼성전자"
    - Ticker codes: "005930"
    
    Note: Cache must be loaded before calling this function.
    """
    from services.company_cache import get_company_cache
    
    cache = get_company_cache()
    if not cache.is_loaded:
        # Fallback to aliases if cache not loaded
        companies = []
        for alias, full_name in COMPANY_ALIASES.items():
            if alias in text and full_name not in companies:
                companies.append(full_name)
        return companies
    
    return cache.find_companies(text)


def _extract_report_types(text: str) -> List[str]:
    """
    Extract report types from text.
    
    Mapping:
    - "사업보고서" → ["annual"]
    - "정기보고서" → ["annual", "semi_annual", "quarterly"]
    """
    for keyword, types in REPORT_TYPE_MAP.items():
        if keyword in text:
            return types
    
    return []
