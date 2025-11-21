"""Recommendation helpers for proactive chat starters."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from core.env import env_int
from models.filing import Filing
from services.memory.facade import MEMORY_SERVICE

RECENT_LOOKBACK_HOURS = env_int("RECO_FILINGS_LOOKBACK_HOURS", 24, minimum=1)
RECENT_SCAN_LIMIT = env_int("RECO_FILINGS_SCAN_LIMIT", 30, minimum=1)
RECO_DEFAULT_LIMIT = env_int("RECO_FILINGS_DEFAULT_LIMIT", 3, minimum=1)
RECO_CACHE_TTL_MINUTES = env_int("RECO_FILINGS_CACHE_TTL_MINUTES", 30, minimum=1)

DEFAULT_STARTERS = [
    "하이브 주가 이벤트 분석 (주요 리스크와 CAR 영향까지 정리해줘)",
    "삼성전자 최근 분기 실적 요약해줘 (매출/영업이익/YoY)",
    "2차전지 섹터 리스크 점검 (IRA 변수 포함)",
]

_cache: Dict[str, Tuple[datetime, List[dict]]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _extract_profile_tokens(user_id: Optional[str]) -> Sequence[str]:
    if not user_id:
        return []
    try:
        summaries = MEMORY_SERVICE.get_session_summaries(f"user:{user_id}")
    except Exception:
        return []
    tokens: List[str] = []
    for entry in summaries:
        for h in entry.highlights:
            parts = [p.strip() for p in h.replace("관심 티커:", "").replace("관심 산업/리스크:", "").split(",")]
            for part in parts:
                if part and part not in tokens:
                    tokens.append(part)
    return tokens


def _format_question(filing: Filing) -> str:
    name = filing.corp_name or filing.ticker or "해당 기업"
    title = filing.report_name or filing.title or filing.category or "최근 공시"
    return f"{name} {title} 핵심 요약과 리스크를 정리해줘"


def _score_filing(filing: Filing, profile_tokens: set[str]) -> float:
    base_score = 1.0
    # Recency boost
    if filing.filed_at:
        age_hours = (_now() - filing.filed_at).total_seconds() / 3600.0
        base_score += max(0.0, (24 - age_hours)) * 0.05
    # Profile match
    if filing.ticker and filing.ticker.upper() in profile_tokens:
        base_score += 5.0
    # Heuristic based on report name keywords
    title = (filing.report_name or filing.title or "").lower()
    if any(key in title for key in ["사업보고서", "분기보고서", "반기보고서"]):
        base_score += 1.0
    if any(key in title for key in ["잠정실적", "실적", "earnings", "1분기", "2분기", "3분기", "4분기"]):
        base_score += 1.5
    if any(key in title for key in ["유상증자", "증자", "cb", "bw", "사채"]):
        base_score += 1.0
    return base_score


def build_recommendations(db: Session, *, user_id: Optional[str], limit: int = RECO_DEFAULT_LIMIT) -> List[dict]:
    """Return recommended starter questions based on recent filings and user profile."""

    limit = max(1, min(limit, 10))
    cache_key = f"filings:{RECENT_LOOKBACK_HOURS}:{RECENT_SCAN_LIMIT}"
    cached = _cache.get(cache_key)
    filings: Sequence[Filing]
    if cached:
        expires_at, payloads = cached
        if _now() < expires_at:
            filings = payloads  # type: ignore[assignment]
        else:
            _cache.pop(cache_key, None)
            filings = []
    else:
        filings = []

    if not filings:
        lookback_start = _now() - timedelta(hours=RECENT_LOOKBACK_HOURS)
        filings = (
            db.query(Filing)
            .filter(Filing.filed_at.isnot(None), Filing.filed_at >= lookback_start)
            .order_by(Filing.filed_at.desc())
            .limit(RECENT_SCAN_LIMIT)
            .all()
        )
        _cache[cache_key] = (_now() + timedelta(minutes=RECO_CACHE_TTL_MINUTES), list(filings))

    profile_tokens = {token.upper() for token in _extract_profile_tokens(user_id)}

    scored: List[tuple[float, dict]] = []
    for filing in filings:
        question = _format_question(filing)
        base_score = _score_filing(filing, profile_tokens)
        scored.append(
            (
                base_score,
                {
                    "question": question,
                    "source": "filing",
                    "ticker": filing.ticker,
                    "corpName": filing.corp_name,
                    "filedAt": filing.filed_at.isoformat() if filing.filed_at else None,
                    "filingId": str(filing.id) if getattr(filing, "id", None) else None,
                },
            )
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    seen_questions = set()
    items: List[dict] = []
    for _, payload in scored:
        if payload["question"] in seen_questions:
            continue
        items.append(payload)
        seen_questions.add(payload["question"])
        if len(items) >= limit:
            break

    if not items:
        items = [{"question": q, "source": "default"} for q in DEFAULT_STARTERS[:limit]]

    return items


def refresh_cache(db: Session) -> int:
    """Refresh the cached filings list for recommendations."""

    lookback_start = _now() - timedelta(hours=RECENT_LOOKBACK_HOURS)
    filings = (
        db.query(Filing)
        .filter(Filing.filed_at.isnot(None), Filing.filed_at >= lookback_start)
        .order_by(Filing.filed_at.desc())
        .limit(RECENT_SCAN_LIMIT)
        .all()
    )
    cache_key = f"filings:{RECENT_LOOKBACK_HOURS}:{RECENT_SCAN_LIMIT}"
    _cache[cache_key] = (_now() + timedelta(minutes=RECO_CACHE_TTL_MINUTES), list(filings))
    return len(filings)


__all__ = ["build_recommendations", "DEFAULT_STARTERS"]
