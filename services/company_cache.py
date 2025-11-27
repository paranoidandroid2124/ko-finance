"""In-memory cache for company names to enable fast natural language search."""

from __future__ import annotations

import re
from typing import Dict, List, Set, Optional

from sqlalchemy import distinct
from sqlalchemy.orm import Session

from db.orm import Filing


class CompanyCache:
    """
    In-memory cache for company names, tickers, and aliases.
    
    Loads all unique companies from the database at startup and provides
    fast lookup for natural language queries.
    """
    
    def __init__(self):
        self._company_names: Set[str] = set()
        self._ticker_to_name: Dict[str, str] = {}
        self._corp_code_to_name: Dict[str, str] = {}
        self._aliases: Dict[str, str] = {}
        self._loaded = False
    
    def load(self, db: Session) -> None:
        """
        Load all unique companies from the database.
        
        This should be called once at application startup.
        """
        if self._loaded:
            return
        
        # Query all unique company/ticker combinations
        results = db.query(
            Filing.company,
            Filing.ticker,
            Filing.corp_code
        ).distinct().all()
        
        for company, ticker, corp_code in results:
            if company:
                self._company_names.add(company)
            
            if ticker and company:
                self._ticker_to_name[ticker.upper()] = company
            
            if corp_code and company:
                self._corp_code_to_name[corp_code] = company
        
        # Load aliases from JSON file
        from pathlib import Path
        import json
        
        alias_file = Path(__file__).parent / "data" / "company_aliases.json"
        try:
            with open(alias_file, "r", encoding="utf-8") as f:
                loaded_aliases = json.load(f)
                # Filter out comments
                self._aliases = {k: v for k, v in loaded_aliases.items() if not k.startswith("_")}
        except FileNotFoundError:
            # Fallback to minimal hardcoded aliases
            self._aliases = {
                "삼전": "삼성전자",
                "하닉": "SK하이닉스",
                "LG전": "LG전자",
                "현차": "현대차",
                "기아차": "기아",
            }
        except Exception as e:
            from core.logger import get_logger
            logger = get_logger(__name__)
            logger.warning(f"Failed to load aliases from JSON: {e}")
            self._aliases = {}
        
        self._loaded = True
    
    def find_companies(self, text: str) -> List[str]:
        """
        Find company names mentioned in the given text.
        
        Checks for:
        1. Aliases (e.g., "삼전" → "삼성전자")
        2. Full company names
        3. Ticker symbols (e.g., "005930")
        
        Args:
            text: Natural language query
        
        Returns:
            List of matched company names
        """
        if not self._loaded:
            return []
        
        found = []
        
        # 1. Check aliases first (highest priority)
        for alias, canonical_name in self._aliases.items():
            if alias in text and canonical_name not in found:
                found.append(canonical_name)
        
        # 2. Check full company names
        for company in self._company_names:
            if company in text and company not in found:
                found.append(company)
        
        # 3. Check ticker symbols (6-digit codes like "005930")
        ticker_matches = re.findall(r'\b\d{6}\b', text)
        for ticker in ticker_matches:
            if ticker in self._ticker_to_name:
                name = self._ticker_to_name[ticker]
                if name not in found:
                    found.append(name)
        
        return found
    
    @property
    def is_loaded(self) -> bool:
        """Check if cache has been loaded."""
        return self._loaded
    
    @property
    def company_count(self) -> int:
        """Get the number of cached companies."""
        return len(self._company_names)


# Global singleton instance
_company_cache: Optional[CompanyCache] = None


def get_company_cache() -> CompanyCache:
    """Get the global company cache instance."""
    global _company_cache
    if _company_cache is None:
        _company_cache = CompanyCache()
    return _company_cache
