"\"\"\"Utilities for classifying news articles into market sectors.\"\"\""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, Iterable, Optional, Tuple

from sqlalchemy.orm import Session

from models.news import NewsSignal
from models.sector import NewsArticleSector, Sector

DEFAULT_SECTOR_SLUG = "others"

SECTOR_DEFINITIONS: Dict[str, str] = {
    "semiconductor": "반도체",
    "hardware": "전자장비/디스플레이",
    "software": "소프트웨어/SaaS",
    "internet": "인터넷/플랫폼",
    "telecom": "통신",
    "media": "미디어/게임/엔터",
    "mobility": "모빌리티/완성차",
    "battery": "2차전지",
    "energy": "에너지/발전/정유",
    "renewables": "신재생에너지/수소",
    "finance": "금융",
    "bio": "바이오/헬스케어",
    "materials": "소재/화학/철강",
    "industrials": "산업재/기계/조선",
    "logistics": "물류/운송",
    "real_estate": "부동산/건설/REITs",
    "defense": "방위산업/항공우주",
    "consumer": "소비재",
    DEFAULT_SECTOR_SLUG: "기타",
}

_SECTOR_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "semiconductor": (
        "반도체",
        "semi",
        "semis",
        "chip",
        "chips",
        "hbm",
        "메모리",
        "memory",
        "dram",
        "낸드",
        "nand",
        "파운드리",
        "foundry",
        "파블리스",
        "fabless",
        "장비",
        "euv",
        "asml",
        "웨이퍼",
        "미세공정",
        "osat",
        "패키징",
        "eda",
    ),
    "hardware": (
        "전자부품",
        "전자장비",
        "디스플레이",
        "oled",
        "lcd",
        "pcb",
        "커넥터",
        "모듈",
        "센서",
        "카메라모듈",
        "mlcc",
        "수동소자",
        "세트업체",
        "가전",
        "tv",
        "모니터",
    ),
    "software": (
        "소프트웨어",
        "saas",
        "클라우드소프트웨어",
        "erp",
        "crm",
        "mes",
        "plm",
        "middleware",
        "api 게이트웨이",
        "구독형",
        "라이선스",
    ),
    "internet": (
        "인터넷",
        "플랫폼",
        "포털",
        "검색",
        "광고",
        "애드테크",
        "커머스",
        "이커머스",
        "마켓플레이스",
        "sns",
        "쇼핑몰",
        "오픈마켓",
        "콘텐츠플랫폼",
        "ugc",
        "크리에이터",
    ),
    "telecom": (
        "통신",
        "이동통신",
        "5g",
        "6g",
        "망",
        "요금제",
        "기지국",
        "광케이블",
        "mvno",
        "백홀",
        "ims",
        "iptv",
    ),
    "media": (
        "미디어",
        "엔터",
        "콘텐츠",
        "게임",
        "게임사",
        "퍼블리싱",
        "개발사",
        "드라마",
        "영화",
        "방송",
        "공연",
        "ott",
        "스트리밍",
        "k-팝",
        "아이돌",
        "e스포츠",
    ),
    "mobility": (
        "모빌리티",
        "자동차",
        "오토모티브",
        "완성차",
        "전기차",
        "ev",
        "자율주행",
        "adas",
        "라이다",
        "v2x",
        "차량용반도체",
        "충전소",
        "충전기",
        "택시",
        "모빌리티서비스",
        "카셰어링",
    ),
    "battery": (
        "2차전지",
        "배터리",
        "리튬이온",
        "li-ion",
        "양극재",
        "음극재",
        "전해질",
        "분리막",
        "셀",
        "팩",
        "bms",
        "lfp",
        "ncm",
        "nca",
        "전고체",
        "니켈",
        "코발트",
        "망간",
        "프리커서",
        "전구체",
    ),
    "energy": (
        "에너지",
        "정유",
        "석유",
        "oil",
        "도시가스",
        "lng",
        "lpg",
        "천연가스",
        "발전",
        "원자력",
        "원전",
        "smr",
        "비축유",
        "전력요금",
        "전력시장",
    ),
    "renewables": (
        "신재생",
        "재생에너지",
        "태양광",
        "태양전지",
        "모듈",
        "인버터",
        "풍력",
        "해상풍력",
        "수소",
        "연료전지",
        "ess",
        "재생 srec",
    ),
    "finance": (
        "금융",
        "은행",
        "bank",
        "증권",
        "운용",
        "자산운용",
        "보험",
        "캐피탈",
        "금융지주",
        "여신",
        "대출",
        "수신",
        "금리",
        "마진",
        "pf대출",
        "핀테크",
        "결제",
        "카드사",
    ),
    "bio": (
        "바이오",
        "헬스케어",
        "제약",
        "pharma",
        "의료",
        "cmo",
        "cdmo",
        "cro",
        "신약",
        "임상",
        "1상",
        "2상",
        "3상",
        "허가",
        "승인",
        "식약처",
        "fda",
        "ema",
        "바이오시밀러",
        "세포치료",
        "car-t",
        "api(원료의약품)",
    ),
    "materials": (
        "소재",
        "화학",
        "케미칼",
        "철강",
        "비철",
        "동",
        "알루미늄",
        "폴리실리콘",
        "실리카",
        "레진",
        "탄소섬유",
        "전구체",
        "그래파이트",
        "석유화학",
        "pet",
        "bpa",
        "에폭시",
    ),
    "industrials": (
        "산업재",
        "제조",
        "설비",
        "기계",
        "공작기계",
        "로봇",
        "fa",
        "공장자동화",
        "중공업",
        "조선",
        "해양플랜트",
        "건설기계",
        "굴삭기",
        "펌프",
        "밸브",
        "산업용",
    ),
    "logistics": (
        "물류",
        "운송",
        "배송",
        "택배",
        "풀필먼트",
        "항공화물",
        "여객",
        "해운",
        "선박",
        "컨테이너",
        "항만",
        "철도",
        "터미널",
        "물류센터",
    ),
    "real_estate": (
        "부동산",
        "건설",
        "주택",
        "건축",
        "토목",
        "인프라",
        "분양",
        "리츠",
        "reits",
        "오피스",
        "상업시설",
        "pf",
    ),
    "defense": (
        "방산",
        "방위산업",
        "국방",
        "전투기",
        "미사일",
        "잠수함",
        "레이더",
        "유도무기",
        "탄약",
        "위성",
        "항공우주",
        "발사체",
        "k-방산",
    ),
    "consumer": (
        "소비",
        "소비재",
        "리테일",
        "유통",
        "생활",
        "식품",
        "화장품",
        "뷰티",
        "의류",
        "패션",
        "편의점",
        "마트",
        "백화점",
        "홈쇼핑",
        "프랜차이즈",
        "가전판매",
    ),
}

_TICKER_SECTOR_SLUGS: Dict[str, str] = {
    # 반도체
    "005930": "semiconductor",  # 삼성전자
    "000660": "semiconductor",  # SK하이닉스
    # 2차전지/배터리
    "006400": "battery",
    "373220": "battery",
    "003670": "battery",
    # 인터넷/플랫폼
    "035420": "internet",
    "035720": "internet",
    # 모빌리티/완성차
    "005380": "mobility",
    "000270": "mobility",
    # 통신
    "017670": "telecom",
    "030200": "telecom",
    "032640": "telecom",
    # 바이오
    "068270": "bio",
    "207940": "bio",
    # 에너지/정유/전력
    "015760": "energy",
    "010950": "energy",
    # 소재/화학/철강
    "051910": "materials",
    "005490": "materials",
    # 미디어/게임
    "036570": "media",
    # 하드웨어/전자 장비
    "066570": "hardware",
}

_WORD_SEPARATOR = re.compile(r"[·∙•ㆍ\-_/]")


def _normalize(text: str) -> str:
    if not text:
        return ""
    lowered = text.lower()
    lowered = _WORD_SEPARATOR.sub(" ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _score_sector(text: str, ticker: Optional[Iterable[str] | str]) -> Dict[str, float]:
    scores: Dict[str, float] = defaultdict(float)

    # ticker prior
    if ticker:
        candidates: Iterable[str]
        if isinstance(ticker, str):
            candidates = (ticker,)
        else:
            candidates = ticker
        for code in candidates:
            slug = _TICKER_SECTOR_SLUGS.get(code.strip())
            if slug:
                scores[slug] += 8.0

    if not text:
        return scores

    normalized_text = _normalize(text)

    # keyword scoring
    for slug, keywords in _SECTOR_KEYWORDS.items():
        for keyword in keywords:
            token = _normalize(keyword)
            if not token:
                continue
            occurrences = normalized_text.count(token)
            if occurrences:
                weight = 1.0
                if len(token) >= 5:
                    weight += 0.5
                if " " in token:
                    weight += 0.5
                scores[slug] += occurrences * weight

    # simple conflict guard (e.g. CAR-T vs. car)
    if "car-t" in normalized_text or "cart 치료" in normalized_text:
        scores["bio"] += 2.0
        scores["mobility"] -= 1.0

    return scores


def resolve_sector_slug(
    topics: Optional[Iterable[str]],
    ticker: Optional[str | Iterable[str]],
    *,
    title: Optional[str] = None,
    body: Optional[str] = None,
) -> str:
    """Resolve a sector slug from provided metadata."""
    text_parts = [part for part in (title, body) if part]
    if topics:
        text_parts.extend(topic for topic in topics if topic)
    combined_text = " ".join(text_parts)

    scores = _score_sector(combined_text, ticker)
    if not scores:
        return DEFAULT_SECTOR_SLUG
    primary = max(scores.items(), key=lambda item: (item[1], item[0]))[0]
    return primary


def ensure_sector_catalog(session: Session) -> Dict[str, Sector]:
    """Ensure default sector rows exist and return a slug->Sector mapping."""
    existing = {
        sector.slug: sector
        for sector in session.query(Sector).order_by(Sector.id.asc()).all()
    }
    missing: list[Sector] = []
    for slug, name in SECTOR_DEFINITIONS.items():
        if slug not in existing:
            sector = Sector(slug=slug, name=name)
            missing.append(sector)
            existing[slug] = sector

    if missing:
        try:
            session.bulk_save_objects(missing)
            session.flush()
        except Exception:
            session.rollback()
            # In case of race (duplicate slug), re-read existing map
            existing = {
                sector.slug: sector
                for sector in session.query(Sector).order_by(Sector.id.asc()).all()
            }

    return existing


def assign_article_to_sector(session: Session, signal: NewsSignal, weight: float = 1.0) -> Optional[NewsArticleSector]:
    """Assign a processed news signal to a sector using heuristics."""
    sectors = ensure_sector_catalog(session)
    slug = resolve_sector_slug(
        signal.topics,
        signal.ticker,
        title=signal.headline,
        body=signal.summary or (signal.evidence or {}).get("rationale"),
    )
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
