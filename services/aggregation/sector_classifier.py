"\"\"\"Utilities for classifying news articles into market sectors.\"\"\""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from models.news import NewsSignal
from models.sector import NewsArticleSector, Sector

DEFAULT_SECTOR_SLUG = "misc"

SECTOR_DEFINITIONS: Dict[str, str] = {
    "semiconductor": "반도체",
    "energy": "에너지",
    "finance": "금융",
    "bio": "바이오",
    "consumer": "소비재",
    "mobility": "모빌리티",
    DEFAULT_SECTOR_SLUG: "기타",
}

_SECTOR_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "semiconductor": ("반도체", "semi", "chip", "hbm", "메모리", "memory"),
    "energy": ("에너지", "energy", "전력", "oil", "gas", "원유"),
    "finance": ("금융", "bank", "은행", "금리", "증권", "보험"),
    "bio": ("바이오", "bio", "제약", "pharma", "의료", "헬스"),
    "consumer": ("소비", "유통", "리테일", "consumer", "생활", "식품"),
    "mobility": ("모빌", "자동차", "car", "전기차", "모빌리티", "모빌"),
}

_TICKER_SECTOR_SLUGS: Dict[str, str] = {
    "005930": "semiconductor",
    "000660": "semiconductor",
    "051910": "consumer",
    "035720": "mobility",
    "035420": "mobility",
    "068270": "bio",
    "207940": "bio",
    "096770": "energy",
}


def _normalize(text: str) -> str:
    return text.strip().lower()


def resolve_sector_slug(topics: Optional[Iterable[str]], ticker: Optional[str]) -> str:
    """Resolve a sector slug from topics or ticker metadata."""
    if topics:
        normalized_topics = [_normalize(topic) for topic in topics if topic and topic.strip()]
        for slug, keywords in _SECTOR_KEYWORDS.items():
            for keyword in keywords:
                keyword_norm = _normalize(keyword)
                if any(keyword_norm in topic for topic in normalized_topics):
                    return slug

    if ticker:
        ticker_key = ticker.strip()
        if ticker_key:
            slug = _TICKER_SECTOR_SLUGS.get(ticker_key)
            if slug:
                return slug

    return DEFAULT_SECTOR_SLUG


def ensure_sector_catalog(session: Session) -> Dict[str, Sector]:
    """Ensure default sector rows exist and return a slug->Sector mapping."""
    existing = {
        sector.slug: sector
        for sector in session.query(Sector).order_by(Sector.id.asc()).all()
    }
    created = False
    for slug, name in SECTOR_DEFINITIONS.items():
        if slug not in existing:
            sector = Sector(slug=slug, name=name)
            session.add(sector)
            existing[slug] = sector
            created = True

    if created:
        session.flush()

    return existing


def assign_article_to_sector(session: Session, signal: NewsSignal, weight: float = 1.0) -> Optional[NewsArticleSector]:
    """Assign a processed news signal to a sector using heuristics."""
    sectors = ensure_sector_catalog(session)
    slug = resolve_sector_slug(signal.topics, signal.ticker)
    sector = sectors[slug]

    existing = (
        session.query(NewsArticleSector)
        .filter(
            NewsArticleSector.article_id == signal.id,
            NewsArticleSector.sector_id == sector.id,
        )
        .one_or_none()
    )
    if existing:
        existing.weight = weight
        return existing

    link = NewsArticleSector(article_id=signal.id, sector_id=sector.id, weight=weight)
    session.add(link)
    session.flush()
    return link
